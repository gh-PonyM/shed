"""Tests for CLI commands functionality."""

from pathlib import Path


from shed.cli import app
from shed.settings import Settings, ProjectConfig


def test_init_command_success(runner, cli_settings_path, temp_settings_dir):
    """Test successful init command where no config was created before"""
    result = runner.invoke(
        app, ["init", "projectA", "--output", str(temp_settings_dir)]
    )
    assert result.exit_code == 0
    assert "Config created in " in result.stdout
    assert "Migration folder initialized" in result.stdout

    # Verify files were created in temp directory
    project_dir = temp_settings_dir / "projectA"
    assert project_dir.exists()
    assert (project_dir / "migrations").exists()
    assert (project_dir / "migrations" / "versions").exists()

    # Verify the config was written correctly by reading it back
    from shed.settings import Settings

    loaded_settings = Settings.from_file(cli_settings_path)

    # Check that projectA was added to the configuration
    assert "projectA" in loaded_settings.projects
    project_config = loaded_settings.projects["projectA"]
    assert project_config.module.relative_to(temp_settings_dir) == Path(
        "projectA/models.py"
    )
    # Should have a development database named after the project
    assert "projectA" in project_config.db
    assert project_config.db["projectA"].connection.type == "sqlite"


def test_init_command_creates_new_project(runner, cli_settings_path, temp_settings_dir):
    """Test init command creates new project when it doesn't exist."""
    result = runner.invoke(
        app, ["init", "newproject", "--output", str(temp_settings_dir)]
    )

    assert result.exit_code == 0
    assert "Config created in " in result.stdout
    assert "Migration folder initialized" in result.stdout

    # Verify files were created in temp directory
    project_dir = temp_settings_dir / "newproject"
    assert project_dir.exists()
    assert (project_dir / "migrations").exists()


def test_init_command_with_force(runner, cli_settings, temp_settings_dir):
    """Test init command with force flag."""
    # First init
    runner.invoke(app, ["init", "projectA", "--output", str(temp_settings_dir)])

    # Second init with force
    result = runner.invoke(
        app, ["init", "projectA", "--force", "--output", str(temp_settings_dir)]
    )

    assert result.exit_code == 0
    assert "Migration folder initialized" in result.stdout


def test_migrate_command_invalid_target_format(runner, cli_settings):
    """Test migrate command with invalid target format."""
    result = runner.invoke(app, ["migrate", "invalid_target"])

    assert result.exit_code == 2
    assert "Project 'invalid_target' not found in projects" in result.stderr

    result = runner.invoke(app, ["migrate", "projectA.foo"])
    assert result.exit_code == 2
    assert "Project 'projectA' has no environment named" in result.stderr


def test_clone_command_success(runner, cli_settings):
    """Test successful clone command between sqlite databases."""
    result = runner.invoke(app, ["clone", "projectA.staging"])
    print(result.stdout)
    assert result.exit_code == 0
    # assert "Cloned staging_db to staging_db (sqlite)" in result.stdout


def test_clone_command_dry_run(runner, cli_settings):
    """Test clone command with dry run."""
    result = runner.invoke(
        app, ["clone", "projectA.staging", "projectA.staging", "--dry-run"]
    )

    assert result.exit_code == 0
    # assert "[DRY RUN] Would clone staging_db to staging_db (sqlite)" in result.stdout


def test_clone_command_invalid_source_format(runner, cli_settings):
    """Test clone command with invalid source format."""
    result = runner.invoke(app, ["clone", "invalid_source", "projectA.staging"])
    assert result.exit_code == 2


def test_clone_command_invalid_target_format(runner, cli_settings):
    """Test clone command with invalid target format."""
    result = runner.invoke(app, ["clone", "projectA.staging", "invalid_target"])

    assert result.exit_code == 2
    assert " Project 'invalid_target' not found" in result.stderr


def test_clone_command_source_project_not_found(runner, cli_settings):
    """Test clone command with non-existent source project."""
    result = runner.invoke(app, ["clone", "nonexistent.staging", "projectA.staging"])

    assert result.exit_code == 2
    assert "Project 'nonexistent' not found" in result.stderr


def test_clone_command_source_environment_not_found(runner, cli_settings):
    """Test clone command with non-existent source environment."""
    result = runner.invoke(app, ["clone", "projectA.nonexistent", "projectA.staging"])

    assert result.exit_code == 2
    assert "Invalid value for 'SRC'" in result.stderr
    assert " Project 'projectA' has no environment named" in result.stderr


def test_clone_command_target_project_not_found(runner, cli_settings):
    """Test clone command with non-existent target project."""
    result = runner.invoke(app, ["clone", "projectA.staging", "nonexistent.staging"])

    assert result.exit_code == 2
    assert "Project 'nonexistent' not found in projects" in result.stderr


def test_clone_command_target_environment_not_found(runner, cli_settings):
    """Test clone command with non-existent target environment."""
    result = runner.invoke(app, ["clone", "projectA.staging", "projectA.nonexistent"])

    assert result.exit_code == 2
    assert "Invalid value for '[TARGET]'" in result.stderr
    assert " Project 'projectA' has no environment" in result.stderr


def test_clone_command_mismatched_database_types(runner, cli_settings):
    """Test clone command with mismatched database types."""
    result = runner.invoke(app, ["clone", "projectA.staging", "projectA.prod"])

    assert result.exit_code == 1
    assert (
        "Database types must match (source: sqlite, target: postgres)" in result.stderr
    )


def test_revision_command_success(runner, cli_settings_path, temp_settings_dir):
    """Test successful revision command using tests/models.py."""
    from pathlib import Path

    # Get the absolute path to tests/models.py
    tests_dir = Path(__file__).parent
    project_name = "testproject"
    source_models_path = (
        tests_dir / "fixtures" / "projects" / "pg_schemas" / "models.py"
    )
    project_dir = temp_settings_dir / project_name
    project_dir.mkdir()
    target_models_path = project_dir / "models.py"
    versions_dir = project_dir / "migrations" / "versions"

    # Copy the test models.py to the temp directory
    import shutil

    shutil.copy2(source_models_path, target_models_path)

    # First, initialize a project with the output directory
    result = runner.invoke(
        app, ["init", project_name, "--output", str(temp_settings_dir)]
    )
    assert result.exit_code == 0
    assert project_dir.is_dir()
    assert versions_dir.is_dir()

    # Verify the project config points to the correct models file
    from shed.settings import Settings

    settings = Settings.from_file(cli_settings_path)
    models_p = settings.projects[project_name].module
    assert models_p.is_absolute(), "Only convert to rel paths on serialize"
    assert settings.settings_path is not None
    assert (
        settings.settings_path.parent / models_p
    ).absolute() == target_models_path.absolute()

    # Create a revision using in memory sqlite db
    result = runner.invoke(
        app, ["revision", project_name, "--message", "Initial migration"]
    )
    print(result.stderr)
    print(result.stdout)
    assert result.exit_code == 0
    assert "Created revision: Initial migration" in result.stdout

    # Check that the revision file was created
    revision_files = list(versions_dir.glob("*.py"))
    assert len(revision_files) == 1

    # Check that the revision file contains expected content
    with open(revision_files[0]) as f:
        content = f.read()
        assert "Initial migration" in content
        assert "def upgrade()" in content
        assert "def downgrade()" in content

    # Migrate
    r = runner.invoke(app, ("migrate", project_name, "--dry-run"))
    assert "flight" not in r.stdout, (
        "The model with a schema set will be excluded for the sql"
    )
    print(r.stdout)
    assert r.exit_code == 0
    r = runner.invoke(app, ["migrate", project_name])
    assert r.exit_code == 0


def clear_revisions(pr_config: ProjectConfig):
    for file in pr_config.versions_dir.glob("*.py"):
        file.unlink()


def test_revision_command_relative_paths(
    temp_dir_runner, cli_settings_path, temp_settings_dir
):
    """Test successful revision command using relative paths and runner changing directory to temp path as pwd"""

    project_name = "testproject"
    env = "homelab"
    out = "projects"

    # Relative path to db
    rel_db_conn = "sqlite:///lab.sqlite"
    assert not cli_settings_path.is_file()
    cmd = ["init", project_name, "-o", out, "--env", env, "-c", rel_db_conn]
    r = temp_dir_runner.invoke(
        app,
        cmd,
        catch_exceptions=True,
    )
    assert r.exit_code == 0, r.stdout
    assert cli_settings_path.is_file()
    s = Settings.from_file(cli_settings_path)
    pr_config = s.projects[project_name]
    print(s.model_dump_json(indent=2))
    conn = pr_config.db[env].connection
    assert conn.get_dsn != rel_db_conn, (
        "DSN must contain absolute path to ensure migrations work"
    )
    models_p = pr_config.module
    assert models_p.is_absolute(), "The models path should be absolute as well"
    dev_db_config = s.get_dev_db(project_name)
    assert dev_db_config is not None, "Development database should be auto-created"
    from shed.settings import SqliteConnection

    assert isinstance(dev_db_config.connection, SqliteConnection)
    dev_db = dev_db_config.connection.db_path
    assert dev_db.is_absolute(), (
        "Loading the settings should convert the dev db path to an absolute path"
    )

    # Empty revision for development db
    assert not dev_db.is_file()
    r = temp_dir_runner.invoke(app, ["revision", project_name], catch_exceptions=True)
    assert r.exit_code == 0, r.stdout
    assert dev_db.is_file()

    # Empty revision for environment db also sqlite but given with relative connection string
    assert isinstance(conn, SqliteConnection)
    assert not conn.db_path.is_file()
    clear_revisions(pr_config)
    r = temp_dir_runner.invoke(
        app, ["revision", f"{project_name}.{env}"], catch_exceptions=True
    )
    assert r.exit_code == 0, r.stdout
    assert conn.db_path.is_file()

    # Migrate
    r = temp_dir_runner.invoke(app, ["migrate", project_name])
    assert r.exit_code == 0
