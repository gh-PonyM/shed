"""Tests for settings module."""

from pathlib import Path


from shed.settings import (
    DatabaseConfig,
    Settings,
    SqliteConnection,
)


def test_sqlite_config_valid():
    """Test valid SQLite configuration."""
    config = DatabaseConfig(
        type="sqlite", connection={"db_path": Path("/path/to/db.sqlite")}
    )
    assert config.type == "sqlite"
    assert isinstance(config.connection, SqliteConnection)


def test_empty_settings_creation():
    """Test creating empty settings."""
    settings = Settings()
    assert settings.development is not None
    assert settings.projects == {}

    settings.development.add_connection("testproject", db_type="sqlite")
    assert settings.development.db["testproject"].connection.db_path == Path(
        "testproject.sqlite"
    )

    settings.development.add_connection(
        "testproject", db_type="postgres", password="foobar"
    )
    assert settings.development.db["testproject"].connection.database == "postgres"
