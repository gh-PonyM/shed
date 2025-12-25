from pathlib import Path
from typing import NamedTuple

import click
import typer
from pydantic import PostgresDsn
from shed.settings import (
    DatabaseConfig,
    SqliteConnection,
    PostgresConnection,
    ProjectConfig,
    Settings,
)


def parse_connection(value: str) -> "DBConnection":
    from sqlalchemy.engine.url import make_url

    parsed = make_url(value)
    if parsed.drivername == "sqlite":
        if not parsed.database:
            raise typer.BadParameter("SQLite URI must include a path")
        # Note that to be added to the settings, the path must be converted to an absolute path
        cfg = DatabaseConfig(
            type="sqlite", connection=SqliteConnection(db_path=Path(parsed.database))
        )

    elif parsed.drivername in {"postgresql", "postgres"}:
        try:
            dsn = PostgresDsn(value)
            host = dsn.hosts()[0]
        except Exception as err:
            raise typer.BadParameter(f"PostgreSQL URI invalid: {err}")
        cfg = DatabaseConfig(
            type="postgres",
            connection=PostgresConnection(
                host=host["host"],
                port=host["port"] or 5432,
                username=host["username"],
                password=host["password"] or "postgres",
                database=dsn.path.lstrip("/"),
            ),
        )
    else:
        raise typer.BadParameter(
            f"Unsupported scheme '{parsed.drivername}'. Only sqlite and postgresql/postgres are supported."
        )
    return DBConnection(cfg)


class DBConnection:
    def __init__(self, value):
        self.value: DatabaseConfig | None = value

    def __bool__(self):
        return bool(self.value)

    def __str__(self):
        t = self.value.type if self.value else "Emtpy"
        return f"DBConnection(type={t})"


class ProjectEnvironment(NamedTuple):
    """Parsed project.environment target."""

    project_name: str
    project_config: ProjectConfig
    db_config: DatabaseConfig
    environment_name: str | None = None


def parse_project_string(settings: Settings, value: str) -> ProjectEnvironment:
    """Validate and parse project.environment format."""
    tokens = value.split(".")
    if len(tokens) > 2:
        raise typer.BadParameter(
            "Target must be in format 'project.environment' or 'project' (for development)"
        )
    project_name, env_name = tokens if len(tokens) == 2 else (tokens[0], None)
    if project_name not in settings.projects:
        raise typer.BadParameter(
            f"Project '{project_name}' not found in projects.",
        )

    project_config = settings.projects[project_name]

    if env_name:
        if env_name not in project_config.db:
            raise typer.BadParameter(
                f"Project '{project_name}' has no environment named '{env_name}'"
            )
        db_config = project_config.db[env_name]
    else:
        # Try to auto-detect development database
        dev_db = settings.get_dev_db(project_name)
        if not dev_db:
            raise typer.BadParameter(
                f"Could not determine development database for project '{project_name}'. "
                f"Either specify environment explicitly (e.g., '{project_name}.env'), "
                f"or ensure there is exactly one database named '{project_name}', 'dev*', or '*dev'."
            )
        db_config = dev_db

    return ProjectEnvironment(
        project_name=project_name,
        environment_name=env_name,
        project_config=project_config,
        db_config=db_config,
    )


class ProjectEnvironParser(click.ParamType):
    name = "ProjectEnvironment"

    def convert(self, value, param, ctx):
        settings: Settings = ctx.obj["settings"]
        return parse_project_string(settings, value)
