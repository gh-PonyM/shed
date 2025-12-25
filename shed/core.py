import contextlib
import importlib.util
import os
import re
import tempfile
from pathlib import Path
from typing import NamedTuple, Any, Callable, Generator, Literal
import importlib
import inspect
from functools import lru_cache
import shutil

import typer
from pydantic import BaseModel
from sqlmodel import SQLModel

from .constants import PROG_NAME
from .settings import (
    DatabaseConfig,
    ProjectConfig,
    Settings,
    SqliteConnection,
    PostgresConnection,
)


def render_template(template: str, **variables: Any) -> str:
    """Poor mans jinja function"""
    result = template
    for key, value in variables.items():
        # Replace {{key}} and {{ key }} patterns (with optional spaces)
        result = re.sub(r"\{\{\s*" + re.escape(key) + r"\s*\}\}", str(value), result)
    return result


class InitResult(NamedTuple):
    """Result of initialization operation."""

    success: bool
    message: str
    config_created: bool = False
    models_path: str | None = None


class MigrateResult(NamedTuple):
    """Result of migration operation."""

    success: bool
    message: str
    sql: str | None = None


class CloneResult(NamedTuple):
    """Result of clone operation."""

    success: bool
    message: str


class RevisionResult(NamedTuple):
    """Result of revision creation operation."""

    success: bool
    message: str
    revision_file: str | None = None


@lru_cache(maxsize=32)
def module_path_root(module: str):
    if isinstance(module, str):
        module = importlib.import_module(module)

    assert module is not None
    return Path(inspect.getfile(module)).parents[0]


templates_path = module_path_root(PROG_NAME) / "templates"


def init_project(
    settings: Settings,
    project_name: str,
    force: bool = False,
    output_dir: Path | None = None,
    db_config: DatabaseConfig | None = None,
    env_name: str = "prod",
    dev_db_type: Literal["sqlite", "postgres"] = "sqlite",
) -> InitResult:
    """Initialize migration folder for a project, creating project config if needed."""
    config_created = False

    # Check if project exists, if not create it, use relative paths to the settings
    s_p = settings.settings_path.parent.resolve()
    if not output_dir:
        output_dir = s_p
    project_dir = (output_dir / project_name).resolve()

    try:
        project_rel_path = project_dir.relative_to(s_p)
    except ValueError:
        typer.secho(f"Project '{project_dir}' is not a subpath of {s_p}", err=True)
        raise typer.Exit(1)

    models_rel_path = project_rel_path / "models.py"
    models_path = project_dir / "models.py"

    if project_name not in settings.projects:
        config_created = True
    project_config = settings.add_project(project_name, models_path)

    # Add production database if provided
    if db_config:
        project_config.db[env_name] = db_config

    # Add development database to the project
    dev_env_name = project_name  # Use project name as default dev environment name
    if dev_db_type == "sqlite":
        dev_connection = SqliteConnection(db_path=s_p / f"{project_name}.sqlite")
        project_config.db[dev_env_name] = DatabaseConfig(connection=dev_connection)
    else:  # postgres
        dev_connection = PostgresConnection(database=project_name)
        project_config.db[dev_env_name] = DatabaseConfig(connection=dev_connection)

    settings.save()

    # Create migrations directory next to the module (always in the parent directory since module is a .py file)
    migrations_dir = project_dir / "migrations"
    if migrations_dir.exists() and not force:
        return InitResult(
            success=False,
            message=f"Migrations directory already exists at {migrations_dir}. Use --force to overwrite.",
            config_created=config_created,
            models_path=str(models_rel_path),
        )

    # Create migrations directory structure
    migrations_dir.mkdir(parents=True, exist_ok=True)
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    dev_db = project_config.db[dev_env_name].db_name

    message_parts = []
    if config_created:
        message_parts.append(f"Config created in {settings.settings_path}")
    message_parts.append(
        f"Migration folder initialized at {migrations_dir} and development db '{dev_db}' added"
    )
    if db_config:
        message_parts.append("Added prod db for project")
    if not models_path.is_file():
        models_path.write_text("# Put your SQLModels in here\n\n")

    return InitResult(
        success=True,
        message="\n".join(message_parts),
        config_created=config_created,
        models_path=str(models_path),
    )


def clone_database(
    src_db_config: DatabaseConfig, tgt_db_config: DatabaseConfig, dry_run: bool = False
) -> CloneResult:
    """Clone database from source to target (assumes same type already validated)."""
    # TODO: Implement actual database cloning logic
    action = "[DRY RUN] Would clone" if dry_run else "Cloned"
    db_type = src_db_config.connection.type
    return CloneResult(
        success=True,
        message=f"{action} {src_db_config.db_name} to {tgt_db_config.db_name} ({db_type})",
    )


@contextlib.contextmanager
def create_temp_dir():
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def create_alembic_temp_files(tmp: Path, models_path: Path, versions_dir: Path) -> None:
    # Create temporary alembic.ini file
    alembic_ini_content = (templates_path / "alembic.ini").read_text()
    # Create temporary env.py file
    env_py_content = (templates_path / "env.py").read_text()
    env_py_content = render_template(
        env_py_content,
        models_path=models_path,
        models_import_path=models_path.stem,
    )
    # Create temporary files

    alembic_ini_path = tmp / "alembic.ini"
    alembic_script_dir = tmp
    alembic_ini_content = render_template(
        alembic_ini_content,
        script_dir=str(alembic_script_dir),
        versions_dir=str(versions_dir),
    )
    alembic_ini_path.write_text(alembic_ini_content)

    # Write env.py to script_location directory
    env_py_path = alembic_script_dir / "env.py"
    env_py_path.write_text(env_py_content)

    script_template = templates_path / "script.py.mako"
    script_template_path = alembic_script_dir / script_template.name
    shutil.copy2(script_template, script_template_path)


def run_alembic(
    cmd: list[str],
    project_cfg: ProjectConfig,
    db_config: DatabaseConfig,
):
    import subprocess

    with create_temp_dir() as tmp:
        create_alembic_temp_files(tmp, project_cfg.module, project_cfg.versions_dir)
        # Run alembic revision command
        cmd = ["alembic", "-c", str(tmp / "alembic.ini"), *cmd]
        env = os.environ.copy()
        env["SHED_CURRENT_DSN"] = db_config.connection.get_dsn
        env["SHED_CURRENT_SCHEMA"] = db_config.connection.schema_name or ""
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(project_cfg.migrations_dir.parent),
            env=env,
        )
    return result


def create_revision(
    project_config: ProjectConfig,
    db_config: DatabaseConfig,
    message: str,
    autogenerate: bool = True,
    use_ruff: bool = True,
) -> RevisionResult:
    """Create a new migration revision using alembic."""
    from .utils import format_with_ruff, is_ruff_available

    migrations_dir = project_config.migrations_dir
    versions_dir = project_config.versions_dir

    # Check if migrations directory exists
    if not migrations_dir.exists():
        return RevisionResult(
            success=False,
            message=f"Migrations directory not found at {migrations_dir}. Run '{PROG_NAME} init' first.",
        )
    cmd = ["revision", "-m", message]
    if autogenerate:
        cmd.append("--autogenerate")
    result = run_alembic(cmd, project_config, db_config)
    if result.returncode != 0:
        return RevisionResult(
            success=False, message=f"Alembic revision failed: {result.stderr}"
        )
    # Find the created revision file
    revision_files = list(versions_dir.glob("*.py"))
    latest_revision = max(revision_files, key=lambda p: p.stat().st_mtime, default=None)

    # Format with ruff if enabled and available
    if use_ruff and latest_revision and is_ruff_available():
        format_with_ruff(latest_revision)

    return RevisionResult(
        success=True,
        message=f"Created revision: {message}",
        revision_file=str(latest_revision) if latest_revision else None,
    )


def migrate_database(
    project_config: ProjectConfig,
    db_config: DatabaseConfig,
    dry_run: bool = False,
    revision: str = "head",
) -> MigrateResult:
    """Run database migrations."""
    cmd = ["upgrade", revision]
    if dry_run:
        # Does not apply migration to db, but emits sql to stdout
        cmd.append("--sql")
    result = run_alembic(cmd, project_config, db_config)
    db_type = db_config.connection.type
    if result.returncode != 0:
        return MigrateResult(
            success=False,
            message=f"Failed to run alembic migrations '{db_config.db_name}' ({db_type}): {result.stderr}",
            sql=result.stdout.strip() if dry_run else None,
        )
    return MigrateResult(
        success=True,
        message=result.stdout
        if dry_run
        else f"Migrated database '{db_config.db_name}' ({db_type})",
    )
    return MigrateResult(
        success=True,
        message=result.stdout
        if dry_run
        else f"Migrated database ‘{db_config.db_name}’ ({db_config.type})",
    )


def exportable_model(m: Any):
    return (
        inspect.isclass(m)
        and issubclass(m, BaseModel)
        and not m == BaseModel
        and not m == SQLModel
    )


def yield_models_by_file(
    file: Path,
    predicate: Callable[[Any], bool] = exportable_model,
) -> Generator[BaseModel, None, None]:
    module_name = file.stem + "_dynamic"
    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for _, obj in inspect.getmembers(module, predicate=predicate):
        yield obj
