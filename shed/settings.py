"""Settings models for schema management."""

from functools import partial
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel as PydanticBaseModel,
    Field,
    field_validator,
    model_validator,
    model_serializer,
    ConfigDict,
)
from urllib.parse import quote_plus

from pydantic_core.core_schema import SerializerFunctionWrapHandler

from shed.constants import DEFAULT_SETTINGS_FN

ConvertMode = Literal["abs", "rel"]


def convert_abs(root: Path, value: Path):
    return value if value.is_absolute() else root / value


def convert_rel(root: Path, value: Path):
    return value.relative_to(root)


def path_convert(root: Path, value: Path, mode: ConvertMode) -> Path:
    return {"abs": partial(convert_abs, root), "rel": partial(convert_rel, root)}[mode](
        value
    )


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid")


class SettingsRelPaths(PydanticBaseModel):
    def _convert_paths(self, path: Path, mode: Literal["rel", "abs"] = "rel"):
        for name, f_info in self.__class__.model_fields.items():
            if f_info.annotation == Path:
                new_val = path_convert(path, getattr(self, name), mode)
                setattr(self, name, new_val)


class SqliteConnection(SettingsRelPaths):
    """SQLite database connection configuration."""

    type: Literal["sqlite"] = "sqlite"
    db_path: Path

    @property
    def get_dsn(self) -> str:
        """Get SQLAlchemy DSN for SQLite connection."""
        return f"sqlite:///{self.db_path}"

    @property
    def schema_name(self) -> str:
        return ""


class PostgresConnection(SettingsRelPaths):
    """PostgreSQL database connection configuration."""

    type: Literal["postgres"] = "postgres"
    host: str = "127.0.0.1"
    port: int = 5432
    username: str = "postgres"
    database: str = "postgres"
    password: str = "postgres"
    schema_name: str | None = Field(
        None, description="Use this schema for migrations if set"
    )

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


class DatabaseConfig(PydanticBaseModel):
    """Database configuration for a specific environment."""

    connection: SqliteConnection | PostgresConnection = Field(discriminator="type")

    @property
    def db_name(self) -> str:
        db = getattr(self.connection, "database", None)
        return db if db else str(self.connection.db_path)


class ProjectConfig(SettingsRelPaths):
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

    def _convert_paths(self, path: Path, mode: Literal["rel", "abs"] = "rel"):
        super()._convert_paths(path, mode)
        for db in self.db.values():
            db.connection._convert_paths(path, mode)


def default_settings_path() -> Path:
    return Path(".") / DEFAULT_SETTINGS_FN


class Settings(BaseModel):
    """Main settings configuration."""

    projects: dict[str, ProjectConfig] = Field(default_factory=dict)

    settings_path: Path | None = None

    def add_project(self, project_name: str, code_path: Path) -> ProjectConfig:
        if not code_path.is_absolute():
            raise ValueError("code_path must be absolute")
        if project_name not in self.projects:
            self.projects[project_name] = ProjectConfig(module=code_path, db={})
        return self.projects[project_name]

    @classmethod
    def from_file(cls, settings_path: Path) -> "Settings":
        """Load settings from file."""
        if not settings_path.exists():
            # Create default settings file
            settings = cls(settings_path=settings_path)
            settings.save()
            return settings
        with open(settings_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        settings = cls(**data, settings_path=settings_path)
        return settings

    def all_code_files(self):
        for name, project in self.projects.items():
            yield name, project.module

    def get_dev_db(self, project_name: str) -> DatabaseConfig | None:
        """Get development database for a project.

        Looks for a database with the same name as the project, or one matching
        'dev*' or '*dev' patterns. Returns None if not found or ambiguous.
        """
        if project_name not in self.projects:
            return None

        project = self.projects[project_name]

        # First, try exact match with project name
        if project_name in project.db:
            return project.db[project_name]

        # Look for dev* or *dev patterns
        dev_candidates = [
            env_name
            for env_name in project.db.keys()
            if env_name.lower().startswith("dev") or env_name.lower().endswith("dev")
        ]

        # Return the db if exactly one dev candidate found
        if len(dev_candidates) == 1:
            return project.db[dev_candidates[0]]

        # Return None if no candidates or multiple candidates (ambiguous)
        return None

    def save(self) -> None:
        """Save settings to file."""
        if not self.settings_path:
            self.settings_path = self._get_settings_path()

        # Ensure directory exists
        self.settings_path.parent.mkdir(exist_ok=True)

        # Re-validate
        data_dump = self.model_dump(exclude={"settings_path"}, mode="json")
        self.__class__(**data_dump)
        with open(self.settings_path, "w", encoding="utf-8") as f:
            yaml.dump(data_dump, f, default_flow_style=False, indent=2)

    def _convert_paths(self, mode: Literal["rel", "abs"] = "rel"):
        root = self.settings_path.parent.absolute()
        for proj in self.projects.values():
            proj._convert_paths(root, mode)

    @model_serializer(mode="wrap")
    def serialize_model(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        if not self.settings_path:
            return handler(self)
        a_copy = self.model_copy(deep=True)
        a_copy._convert_paths(mode="rel")
        serialized = handler(a_copy)
        return serialized

    @model_validator(mode="after")
    def validate_paths(self):
        if self.settings_path:
            self._convert_paths(mode="abs")
        return self
