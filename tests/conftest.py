import shutil
import tempfile
from os import getenv
from pathlib import Path
from traceback import print_tb

import psycopg2
import pytest
import yaml
from typer.testing import CliRunner as BaseCliRunner

from shed.constants import SETTINGS_PATH_ENV_VAR, DEFAULT_SETTINGS_FN
from shed.custom_types import parse_project_string
from shed.settings import PostgresConnection, Settings
from shed.utils import cd_to_directory


class CliRunner(BaseCliRunner):
    with_traceback = True

    def invoke(self, cli, commands, **kwargs):
        result = super().invoke(cli, commands, **kwargs)
        if not result.exit_code == 0 and self.with_traceback:
            print_tb(result.exc_info[2])
            print(result.exception)
            print(result.stderr)
        return result


@pytest.fixture
def temp_settings_dir():
    """Create a temporary directory for settings."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def cli_settings_path(temp_settings_dir, monkeypatch):
    """Create settings for CLI testing with environment variable set."""
    settings_path = temp_settings_dir / "test_settings.yaml"
    monkeypatch.setenv(SETTINGS_PATH_ENV_VAR, str(settings_path))
    return settings_path


@pytest.fixture
def cli_settings(cli_settings_path, monkeypatch, sample_settings_data):
    """Create settings for CLI testing with environment variable set."""
    # Return loaded settings instance
    cli_settings_path.write_text(yaml.safe_dump(sample_settings_data))
    s = Settings.from_file(cli_settings_path)
    return s


@pytest.fixture
def sample_settings_data(temp_settings_dir):
    """Sample settings data for testing."""
    return {
        "projects": {
            "projectA": {
                "module": "tests/fixtures/models.py",
                "db": {
                    "projectA": {
                        "connection": {
                            "db_path": str(temp_settings_dir / "shed-dev.sqlite"),
                            "type": "sqlite",
                        },
                    },
                    "staging": {
                        "connection": {
                            "type": "sqlite",
                            "db_path": str(temp_settings_dir / "staging.sqlite"),
                        },
                    },
                    "prod": {
                        "connection": {
                            "host": "prod.example.com",
                            "port": 5432,
                            "username": "prod_user",
                            "password": "prod_pass",
                            "database": "prod_db",
                            "type": "postgres",
                        },
                    },
                },
            }
        },
    }


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir_runner(temp_settings_dir):
    """Create CLI test runner."""
    with cd_to_directory(temp_settings_dir):
        yield CliRunner()


def get_db_host():
    return getenv("SHED_TEST_DB_HOST", "")


def copy_project_files(project_name: str, temp_settings_dir) -> Path:
    """Copies a test project in a temp dir"""
    fixtures_dir = Path(__file__).parent / "fixtures"
    shutil.copytree(fixtures_dir, temp_settings_dir, dirs_exist_ok=True)
    target_config = temp_settings_dir / DEFAULT_SETTINGS_FN
    shutil.move(temp_settings_dir / f"{project_name}.yml", target_config)
    return target_config


class ProjectHelper:
    def __init__(self, settings: Settings, project_name: str):
        self.settings = settings
        dev_db = settings.get_dev_db(project_name)
        if not dev_db:
            raise ValueError(
                f"No development database found for project {project_name}"
            )
        if not isinstance(dev_db.connection, PostgresConnection):
            raise ValueError(
                f"ProjectHelper requires a PostgreSQL database, got {dev_db.connection.type}"
            )
        self.current_db_conn: PostgresConnection = dev_db.connection
        self.project_name: str = project_name
        self.current_target = project_name
        self.created_schemas: list[str] = []
        self._connection = None

    def _get_conn_params(self, database: str | None = None) -> dict:
        """Build connection parameters for psycopg2."""
        return {
            "host": self.current_db_conn.host,
            "port": self.current_db_conn.port,
            "user": self.current_db_conn.username,
            "password": self.current_db_conn.password,
            "database": database or self.current_db_conn.database,
        }

    def _close_connection(self):
        """Close the current connection if open."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def _get_connection(self):
        """Get or create a database connection."""
        if not self._connection or self._connection.closed:
            self._connection = psycopg2.connect(**self._get_conn_params())
            self._connection.autocommit = False
        return self._connection

    def set_search_path(self, schema_name: str):
        """Set the search_path for the current connection to target a specific schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f'SET search_path TO "{schema_name}"')
            conn.commit()
        finally:
            cursor.close()

    def _run_sql(self, sql: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            conn.commit()
        finally:
            cursor.close()

    def _run_sql_with_autocommit(self, sql: str, database: str | None = None):
        """Run SQL with autocommit enabled (for DDL operations like DROP DATABASE)."""
        conn = psycopg2.connect(**self._get_conn_params(database))
        conn.autocommit = True
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
        finally:
            cursor.close()
            conn.close()

    def create_schema(self, name: str):
        """Create a PostgreSQL schema."""
        self._run_sql(f'CREATE SCHEMA IF NOT EXISTS "{name}"')
        if name not in self.created_schemas:
            self.created_schemas.append(name)

    def drop_schema(self, name: str):
        """Drop a PostgreSQL schema."""
        self._run_sql(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')
        if name in self.created_schemas:
            self.created_schemas.remove(name)

    def teardown(self):
        """Clears the database for all operations made."""
        self._close_connection()
        # Connect to 'postgres' database to drop/recreate the target database
        for sql in (
            f'DROP DATABASE IF EXISTS "{self.current_db_conn.database}"',
            f'CREATE DATABASE "{self.current_db_conn.database}"',
            "DROP TABLE IF EXISTS public.alembic_version",
        ):
            self._run_sql_with_autocommit(
                sql,
                database="postgres",
            )

    def select_target(self, target: str):
        """Select a db connection as you would with shed myproject.env or myproject."""
        # Parse target (e.g., "lab" or "lab.prod")
        pr_env = parse_project_string(self.settings, target)
        if not isinstance(pr_env.db_config.connection, PostgresConnection):
            raise ValueError(
                f"ProjectHelper requires a PostgreSQL database, got {pr_env.db_config.connection.type}"
            )
        self.current_db_conn = pr_env.db_config.connection
        self.current_target = target
        self._close_connection()

    @property
    def versions_dir(self):
        """Return the path to the directories where revisions are generated."""
        return self.settings.projects[self.project_name].versions_dir

    @property
    def revision_files(self):
        return sorted(
            self.versions_dir.glob("*.py"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

    @property
    def last_revision_content(self):
        return self.revision_files[0].read_text(encoding="utf-8")

    def clear_revisions(self):
        for file in self.versions_dir.glob("*.py"):
            file.unlink()

    def create_dummy_table(self, name, schema="public"):
        self.set_search_path(schema)
        self._run_sql(f"""
        CREATE TABLE "{name}" (
          id SERIAL NOT NULL, 
          name VARCHAR NOT NULL, 
          PRIMARY KEY (id)
        );
        """)

    def _query_sql(self, sql: str, params: tuple = ()) -> list:
        """Execute a SQL query and return results."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()

    def get_tables_in_schema(self, schema_name: str) -> list[str]:
        """Get all tables in a specific schema."""
        self.set_search_path(schema_name)
        sql = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            ORDER BY table_name
        """
        results = self._query_sql(sql, (schema_name,))
        return [row[0] for row in results] if results else []

    def table_exists(self, table_name: str, schema_name: str | None = None) -> bool:
        """Check if a table exists in a specific schema."""
        if schema_name:
            self.set_search_path(schema_name)
            sql = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = %s 
                    AND table_name = %s
                )
            """
            results = self._query_sql(sql, (schema_name, table_name))
        else:
            sql = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """
            results = self._query_sql(sql, (table_name,))
        return results[0][0] if results else False


@pytest.fixture
def pg_schemas_project(temp_settings_dir):
    config_path = copy_project_files("pg_schemas", temp_settings_dir)
    helper = ProjectHelper(Settings.from_file(config_path), "lab")
    helper.create_schema("aviation")
    helper.create_schema("prod")
    yield helper
    helper.teardown()
