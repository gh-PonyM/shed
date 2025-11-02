"""Tests for CLI commands functionality."""

from shed.cli import app


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
    assert project_config.module == temp_settings_dir / "projectA" / "models.py"
    assert project_config.db == {}  # Should be empty dict for new project


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


#
# def test_migrate_command_with_message(runner, cli_settings):
#     """Test migrate command with message option."""
#     result = runner.invoke(
#         app, ["migrate", "projectA.staging", "--message", "Test migration"]
#     )
#
#     assert result.exit_code == 0
#     assert "Migrated database " in result.stdout
#
#
# def test_migrate_command_with_revision(runner, cli_settings):
#     """Test migrate command with revision option."""
#     result = runner.invoke(app, ["migrate", "projectA.staging", "--revision", "abc123"])
#
#     assert result.exit_code == 0
#     assert "Migrated database " in result.stdout


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
    source_models_path = tests_dir / "fixtures" / "models.py"
    project_dir = temp_settings_dir / project_name
    project_dir.mkdir()
    target_models_path = project_dir / "models.py"
    versions_dir = project_dir / "migrations" / "versions"

    # Copy the test models.py to the temp directory
    import shutil

    shutil.copy2(source_models_path, project_dir / "models.py")

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
    assert settings.projects[project_name].module == target_models_path.absolute()

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
