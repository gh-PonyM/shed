from logging.config import fileConfig
from sqlalchemy import engine_from_config, text
from sqlalchemy import pool
from alembic import context
import sys
import os
from pathlib import Path

# Add the project module to Python path
sys.path.insert(0, str(Path("{{ models_path }}").parent))

# Import the models
from {{ models_import_path }} import *
from sqlmodel import SQLModel
import re

target_metadata = SQLModel.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def get_dsn_from_env():
    """Get DSN from SHED_CURRENT_DSN environment variable."""
    dsn = os.getenv("SHED_CURRENT_DSN")
    if not dsn:
        raise ValueError("SHED_CURRENT_DSN environment variable is not set")
    return dsn


def get_tenant():
    schema = os.getenv("SHED_CURRENT_SCHEMA", "")
    if schema:
        m = re.match(r"^[a-z_]+$", schema)
        if not m:
            raise ValueError(f"schema is not valid")
        return m.group(0)
    return schema


def run_migrations_offline() -> None:
    # Use DSN from environment variable if available, otherwise fall back to config
    try:
        url = get_dsn_from_env()
    except ValueError:
        url = config.get_main_option("sqlalchemy.url")

    tenant = get_tenant()
    configure_kwargs = {}
    if tenant:
        configure_kwargs["version_table_schema"] = tenant
        configure_kwargs["include_schemas"] = True

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **configure_kwargs
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # Get configuration section
    configuration = config.get_section(config.config_ini_section, {})

    # Override sqlalchemy.url with environment variable if available
    try:
        configuration["sqlalchemy.url"] = get_dsn_from_env()
    except ValueError:
        # If environment variable is not set, use the one from config file
        pass
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    current_tenant = get_tenant()

    with connectable.connect() as connection:
        if current_tenant:
            if connection.dialect.name == "postgresql":
                # set search path on the connection, which ensures that
                # PostgreSQL will emit all CREATE / ALTER / DROP statements
                # in terms of this schema by default

                connection.execute(text('set search_path to "%s"' % current_tenant))
                # in SQLAlchemy v2+ the search path change needs to be committed
                connection.commit()
            elif connection.dialect.name in ("mysql", "mariadb"):
                # set "USE" on the connection, which ensures that
                # MySQL/MariaDB will emit all CREATE / ALTER / DROP statements
                # in terms of this schema by default

                connection.execute(text('USE %s' % current_tenant))

                # make use of non-supported SQLAlchemy attribute to ensure
                # the dialect reflects tables in terms of the current tenant name
            connection.dialect.default_schema_name = current_tenant
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()