"""Settings models for schema management."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, PrivateAttr
from urllib.parse import quote_plus

from shed.constants import DEFAULT_SETTINGS_FN

DBType = Literal["sqlite", "postgres"]


class SqliteConnection(BaseModel):
    """SQLite database connection configuration."""

    db_path: Path

    @property
    def get_dsn(self) -> str:
        """Get SQLAlchemy DSN for SQLite connection."""
        return f"sqlite:///{self.db_path}"


class PostgresConnection(BaseModel):
    """PostgreSQL database connection configuration."""

    host: str = "127.0.0.1"
    port: int = 5432
    username: str = "postgres"
    database: str = "postgres"
    password: str = "postgres"

    @property
    def get_dsn(self) -> str:
        """Get SQLAlchemy DSN for PostgreSQL connection."""
        # URL encode the password to handle special characters
        encoded_password = quote_plus(self.password)
        return f"postgresql://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"

    @field_validator("database")
    @classmethod
    def validate_db_name(cls, v: str) -> str:
        if " " in v:
            raise ValueError("Database name cannot contain spaces")
        return v


class DatabaseConfig(BaseModel):
    """Database configuration for a specific environment."""

    type: DBType
    connection: SqliteConnection | PostgresConnection

    @property
    def db_name(self):
        return getattr(self.connection, "database", self.connection.db_path)


class ProjectConfig(BaseModel):
    """Configuration for a specific project."""

    module: Path = Field(
        ..., description="Path to Python module containing DB Model definitions"
    )
    db: dict[str, DatabaseConfig] = Field(..., description="Database environments")

    @property
    def versions_dir(self):
        return self.migrations_dir / "versions"

    @property
    def migrations_dir(self):
        return self.module.parent / "migrations"


class DevelopmentConfig(BaseModel):
    """Development database configuration."""

    db: dict[str, DatabaseConfig] = Field(default_factory=dict)

    @staticmethod
    def connection_sqlite(project_name: str, **unused):
        return {
            project_name: DatabaseConfig(
                type="sqlite",
                connection=SqliteConnection(db_path=f"{project_name}.sqlite"),
            )
        }

    @staticmethod
    def connection_postgres(project_name: str, **connection_args):
        return {
            project_name: DatabaseConfig(
                type="postgres", connection=PostgresConnection(**connection_args)
            )
        }

    def add_connection(self, project_name: str, db_type: DBType, **connection_args):
        fn_map = {
            "sqlite": self.connection_sqlite,
            "postgres": self.connection_postgres,
        }
        self.db.update(fn_map[db_type](project_name, **connection_args))


def default_settings_path() -> Path:
    return Path(".") / DEFAULT_SETTINGS_FN


class Settings(BaseModel):
    """Main settings configuration."""

    development: DevelopmentConfig = DevelopmentConfig()
    projects: dict[str, ProjectConfig] = Field(default_factory=dict)

    _settings_path: Path | None = PrivateAttr(default_factory=default_settings_path)

    def add_project(self, project_name: str, code_path: Path) -> ProjectConfig:
        if project_name not in self.projects:
            self.projects[project_name] = ProjectConfig(module=code_path, db={})
        return self.projects[project_name]

    @classmethod
    def from_file(cls, settings_path: Path) -> "Settings":
        """Load settings from file."""
        if not settings_path.exists():
            # Create default settings file
            settings = cls()
            settings._settings_path = settings_path
            settings.save()
            return settings

        with open(settings_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        settings = cls(**data)
        settings._settings_path = settings_path
        return settings

    def all_code_files(self):
        for name, project in self.projects.items():
            yield name, project.module

    def save(self) -> None:
        """Save settings to file."""
        if not self._settings_path:
            self._settings_path = self._get_settings_path()

        # Ensure directory exists
        self._settings_path.parent.mkdir(exist_ok=True)

        # Re-validate
        data_dump = self.model_dump(exclude={"_settings_path"}, mode="json")
        self.__class__(**data_dump)
        with open(self._settings_path, "w", encoding="utf-8") as f:
            yaml.dump(data_dump, f, default_flow_style=False, indent=2)
