import shutil
import tempfile
from os import getenv
from pathlib import Path
from traceback import print_tb

import pytest
import yaml
from typer.testing import CliRunner as BaseCliRunner

from shed.constants import SETTINGS_PATH_ENV_VAR
from shed.utils import cd_to_directory
from shed.settings import Settings


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
        "development": {
            "db": {
                "projectA": {
                    "type": "sqlite",
                    "connection": {
                        "db_path": str(temp_settings_dir / "shed-dev.sqlite")
                    },
                },
                "pglocal": {
                    "type": "postgres",
                    "connection": {
                        "host": "localhost",
                        "port": 5433,
                        "username": "dev",
                        "password": "dev_pass",
                        "database": "dev_db",
                    },
                },
            }
        },
        "projects": {
            "projectA": {
                "module": "tests/fixtures/models.py",
                "db": {
                    "staging": {
                        "type": "sqlite",
                        "connection": {
                            "db_path": str(temp_settings_dir / "staging.sqlite")
                        },
                    },
                    "prod": {
                        "type": "postgres",
                        "connection": {
                            "host": "prod.example.com",
                            "port": 5432,
                            "username": "prod_user",
                            "password": "prod_pass",
                            "database": "prod_db",
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
