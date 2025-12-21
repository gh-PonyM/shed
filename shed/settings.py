"""Settings models for schema management."""

from functools import partial
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    model_serializer,
)
from urllib.parse import quote_plus

from pydantic_core.core_schema import SerializerFunctionWrapHandler

from shed.constants import DEFAULT_SETTINGS_FN

DBType = Literal["sqlite", "postgres"]
ConvertMode = Literal["abs", "rel"]


def convert_abs(root: Path, value: Path):
    return value if value.is_absolute() else root / value


def convert_rel(root: Path, value: Path):
    return value.relative_to(root)


def path_convert(root: Path, value: Path, mode: ConvertMode) -> Path:
    return {"abs": partial(convert_abs, root), "rel": partial(convert_rel, root)}[mode](
        value
    )


class SettingsRelPaths(BaseModel):
    def _convert_paths(self, path: Path, mode: Literal["rel", "abs"] = "rel"):
        for name, f_info in self.__class__.model_fields.items():
            if f_info.annotation == Path:
                new_val = path_convert(path, getattr(self, name), mode)
                setattr(self, name, new_val)


class SqliteConnection(SettingsRelPaths):
    """SQLite database connection configuration."""

    db_path: Path

    @property
    def get_dsn(self) -> str:
        """Get SQLAlchemy DSN for SQLite connection."""
        return f"sqlite:///{self.db_path}"


class PostgresConnection(SettingsRelPaths):
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


def connection_sqlite(
    project_name: str, dev_db_dir: Path, **unused
) -> dict[str, DatabaseConfig]:
    return {
        project_name: DatabaseConfig(
            type="sqlite",
            connection=SqliteConnection(db_path=dev_db_dir / f"{project_name}.sqlite"),
        )
    }


def connection_postgres(
    project_name: str, **connection_args
) -> dict[str, DatabaseConfig]:
    return {
        project_name: DatabaseConfig(
            type="postgres", connection=PostgresConnection(**connection_args)
        )
    }


class DevelopmentConfig(BaseModel):
    """Development database configuration."""

    db: dict[str, DatabaseConfig] = Field(default_factory=dict)

    def add_connection(
        self,
        project_name: str,
        db_type: DBType,
        dev_db_dir: Path | None = None,
        **connection_args,
    ):
        fn_map = {
            "sqlite": connection_sqlite,
            "postgres": connection_postgres,
        }
        if db_type == "sqlite" and not dev_db_dir:
            raise ValueError(
                "For sqlite, set the parent directory of the db with 'dev_db_dir'"
            )
        if dev_db_dir:
            connection_args.update({"dev_db_dir": dev_db_dir.absolute()})
        self.db.update(fn_map[db_type](project_name, **connection_args))


def default_settings_path() -> Path:
    return Path(".") / DEFAULT_SETTINGS_FN


class Settings(BaseModel):
    """Main settings configuration."""

    development: DevelopmentConfig = DevelopmentConfig()
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
        for db_config in self.development.db.values():
            db_config.connection._convert_paths(root, mode)

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
