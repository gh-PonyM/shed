"""Tests for settings module."""

from pathlib import Path

import yaml

from shed.settings import (
    DatabaseConfig,
    Settings,
    SqliteConnection,
    PostgresConnection,
)


def test_sqlite_config_valid():
    """Test valid SQLite configuration."""
    config = DatabaseConfig(
        type="sqlite", connection={"db_path": Path("/path/to/db.sqlite")}
    )
    assert config.type == "sqlite"
    assert isinstance(config.connection, SqliteConnection)
    assert isinstance(config.db_name, str)


def test_pg_config_valid():
    """Test valid SQLite configuration."""
    config = DatabaseConfig(type="postgres", connection={})
    assert config.type == "postgres"
    assert isinstance(config.connection, PostgresConnection)
    assert isinstance(config.db_name, str)


def test_empty_settings_creation():
    """Test creating empty settings."""
    settings = Settings()
    assert settings.development is not None
    assert settings.projects == {}

    settings.development.add_connection(
        "testproject", db_type="sqlite", dev_db_dir=Path()
    )
    assert (
        settings.development.db["testproject"].connection.db_path
        == Path("testproject.sqlite").absolute()
    )

    settings.development.add_connection(
        "testproject", db_type="postgres", password="foobar"
    )
    assert settings.development.db["testproject"].connection.database == "postgres"


def test_settings_path_handling(sample_settings_data, temp_settings_dir):
    # Load without settings path
    s = Settings(**sample_settings_data)
    assert not s.projects["projectA"].module.is_absolute()

    # Empty config generation as it would happen on cli invocation
    p = temp_settings_dir / "settings.yaml"
    Settings.from_file(p)

    # Non-empty config with paths
    p.write_text(yaml.safe_dump(sample_settings_data))
    s = Settings.from_file(p)
    print(s.model_dump_json(indent=2))

    s_root = s.settings_path.parent
    pr_a = s.projects["projectA"]
    assert pr_a.module.is_absolute(), (
        "The path should be converted to absolute paths in validator"
    )
    assert pr_a.module.relative_to(s_root)

    serialized = s.model_dump(mode="json")
    pr_a_s = serialized["projects"]["projectA"]
    assert not pr_a_s["module"].startswith("/"), (
        "The serialized path should be relative"
    )
