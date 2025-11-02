"""Tests for CLI help functionality."""

from shed.cli import app


def test_main_help(runner, cli_settings):
    """Test main help command."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert (
        "A command line tool for managing database schemas and migrations"
        in result.stdout
    )
    assert "init" in result.stdout
    assert "migrate" in result.stdout
    assert "clone" in result.stdout


def test_no_args_shows_help(runner, cli_settings):
    """Test that running with no args shows help."""
    result = runner.invoke(app, [])

    assert result.exit_code == 2
    assert "Usage:" in result.stdout


def test_init_help(runner, cli_settings):
    """Test init command help."""
    result = runner.invoke(app, ["init", "--help"])

    assert result.exit_code == 0
    assert "Initialize migration folder for a project" in result.stdout
    assert "project_name" in result.stdout
    assert "--force" in result.stdout


def test_migrate_help(runner, cli_settings):
    """Test migrate command help."""
    result = runner.invoke(app, ["migrate", "--help"])

    assert result.exit_code == 0
    assert "Run database migrations" in result.stdout
    assert "target" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--revision" in result.stdout


def test_clone_help(runner, cli_settings):
    """Test clone command help."""
    result = runner.invoke(app, ["clone", "--help"])

    assert result.exit_code == 0
    assert "Clone database from source to target" in result.stdout
    assert "source" in result.stdout
    assert "target" in result.stdout
    assert "--dry-run" in result.stdout


def test_settings_path_option(runner, cli_settings):
    """Test settings path option in help."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--settings-path" in result.stdout
