"""Tests for CLI commands functionality."""

import pytest

from shed.cli import app
from tests.conftest import get_db_host
import re


def revision(runner, target, msg):
    return runner.invoke(
        app,
        ["revision", target, "--message", msg, "--no-use-ruff"],
    )


def migrate_dry_run(runner, target):
    return runner.invoke(
        app,
        ["migrate", target, "--dry-run"],
    )


def migrate(runner, target):
    return runner.invoke(
        app,
        ["migrate", target],
    )


@pytest.mark.skipif(
    condition=not get_db_host(),
    reason="environment variable for testing with postgres not set",
)
def test_pg_no_schema(temp_dir_runner, pg_schemas_project):
    """Test postgres migration using sample_settings_data."""
    pr = pg_schemas_project
    # Create a revision for postgres prod environment
    commit_msg = "Initial postgres migration"
    target = "lab"
    pr.select_target(target)
    result = revision(temp_dir_runner, target, commit_msg)
    assert result.exit_code == 0

    # show history
    r = temp_dir_runner.invoke(
        app,
        [
            "alembic",
            target,
            "history",
        ],
    )
    assert r.exit_code == 0
    print(r.stdout)
    assert commit_msg in r.stdout

    # The command might fail if postgres is not running, so we check for either success
    # or a meaningful postgres connection error
    assert result.exit_code == 0
    assert "Created revision: Initial postgres migration" in result.stdout
    # Check that the revision file was created
    revision_files = pr.revision_files
    assert len(revision_files) == 1

    # Check that the revision file contains expected content
    content = pr.last_revision_content
    assert "Initial postgres migration" in content
    assert "def upgrade()" in content
    assert "def downgrade()" in content
    print(content)
    assert "op.drop_table('flight', schema='aviation')" in content, (
        "Must contain the schema if on the model"
    )
    tables = re.findall(r"op\.create_table", content)
    assert not pr.current_db_conn.schema_name
    assert len(tables) == 3, (
        "All tables should be added since not schema is selected for the target"
    )

    # Emit sql
    r = temp_dir_runner.invoke(app, ["migrate", target, "--dry-run"])
    assert r.exit_code == 0
    assert "CREATE TABLE alembic_version" in r.stdout, "Should not contain a schema"
    assert 'CREATE TABLE "user"' in r.stdout
    assert "CREATE TABLE post" in r.stdout
    r = temp_dir_runner.invoke(app, ["migrate", target])
    assert r.exit_code == 0

    # Check that tables exist in the 'public' schema (default when no schema specified)
    public_tables = pr.get_tables_in_schema("public")
    assert "alembic_version" in public_tables, (
        "Alembic version table should be in public schema"
    )
    assert "user" in public_tables, "User table should be in public schema"
    assert "post" in public_tables, "Post table should be in public schema"

    # Check that Flight table is in the 'aviation' schema (due to __table_args__)
    aviation_tables = pr.get_tables_in_schema("aviation")
    assert "flight" in aviation_tables, "Flight table should be in aviation schema"

    # Ensure tables are NOT in the 'prod' schema (since we're targeting 'lab')
    prod_tables = pr.get_tables_in_schema("prod")
    assert "user" not in prod_tables, "User table should not be in prod schema"
    assert "post" not in prod_tables, "Post table should not be in prod schema"
    assert "alembic_version" not in prod_tables, (
        "Alembic version table should not be in prod schema"
    )


@pytest.mark.skipif(
    condition=not get_db_host(),
    reason="environment variable for testing with postgres not set",
)
def test_no_schema(temp_dir_runner, pg_schemas_project):
    """Test postgres migration using sample_settings_data."""
    pr = pg_schemas_project
    pr.create_dummy_table("foobar", schema="public")
    # Create a revision for postgres prod environment
    commit_msg = "Initial postgres migration"
    target = "lab"
    pr.select_target(target)
    result = revision(temp_dir_runner, target, commit_msg)
    assert result.exit_code == 0
    content = pr.last_revision_content
    assert "foobar" in content, "Would drop the table if not added by migrations"


@pytest.mark.skipif(
    condition=not get_db_host(),
    reason="environment variable for testing with postgres not set",
)
def test_schema_prod(temp_dir_runner, pg_schemas_project):
    pr = pg_schemas_project
    pr.create_dummy_table("foobar", schema="public")
    pr.create_dummy_table("delete_me", schema="prod")

    target = "lab.prod"
    r = revision(temp_dir_runner, target, "prod using a schema")
    assert r.exit_code == 0
    assert "alembic_version" in pr.get_tables_in_schema("prod")
    assert "alembic_version" not in pr.get_tables_in_schema("public")

    content = pr.last_revision_content
    assert "op.create_table('flight'" in content, "This model is also included"
    assert "foobar" not in content, "foobar is in another schema, no drop table foobar"
    assert "delete_me" in content

    r = migrate_dry_run(temp_dir_runner, target)
    assert r.exit_code == 0
    assert "INSERT INTO alembic_version" in r.stdout, (
        "We set the search path on migration, should not include the tenant in sql"
    )
    print(r.stdout)
    r = migrate(temp_dir_runner, target)
    assert r.exit_code == 0

    # Check that tables exist in the 'prod' schema
    prod_tables = pr.get_tables_in_schema("prod")
    assert "alembic_version" in prod_tables, (
        "Alembic version table should be in prod schema"
    )
    assert "user" in prod_tables, "User table should be in prod schema"
    assert "post" in prod_tables, "Post table should be in prod schema"

    # Check that Flight table is in the 'aviation' schema (due to __table_args__)
    aviation_tables = pr.get_tables_in_schema("aviation")
    assert "flight" in aviation_tables, "Flight table should be in aviation schema"

    # Ensure no tables are in the 'public' schema (all should be in their respective schemas)
    public_tables = pr.get_tables_in_schema("public")
    assert "user" not in public_tables, "User table should not be in public schema"
    assert "post" not in public_tables, "Post table should not be in public schema"
    assert "alembic_version" not in public_tables, (
        "Alembic version table should not be in public schema"
    )
