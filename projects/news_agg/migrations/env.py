from logging.config import fileConfig
from sqlalchemy import engine_from_config, text
from sqlalchemy import pool
from alembic import context
import sys
import os
from pathlib import Path
import logging
from functools import lru_cache

# Add the project module to Python path
sys.path.insert(0, str(Path("models.py").parent))

# Import the models
from models import *
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


@lru_cache(maxsize=1)
def get_tenant() -> str | None:
    """Get tenant/schema from -x tenant argument or SHED_CURRENT_SCHEMA env var.

    When templates are extracted, use: alembic -x tenant=some_schema revision -m "rev1" --autogenerate
    When using shed commands, the SHED_CURRENT_SCHEMA env var is used.
    """
    # Try -x argument first (for extracted/standalone alembic usage)
    tenant = context.get_x_argument(as_dictionary=True).get("tenant")
    if tenant:
        m = re.match(r"^[a-z_]+$", tenant)
        if not m:
            raise ValueError(f"tenant is not valid: {tenant}")
        return m.group(0)

    # Fall back to environment variable (for shed command usage)
    schema = os.getenv("SHED_CURRENT_SCHEMA", "")
    if schema:
        m = re.match(r"^[a-z_]+$", schema)
        if not m:
            raise ValueError(f"schema is not valid: {schema}")
        return m.group(0)
    return None


def get_logger():
    path = os.getenv("SHED_ALEMBIC_LOG_FILE")
    logger = logging.getLogger(__name__)
    if not path:
        # Return a no-op logger if no log file is configured
        logger.addHandler(logging.NullHandler())
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(path)
    handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(filename)s:%(lineno)d %(message)s")
    )
    logger.addHandler(handler)
    return logger


log = get_logger()


def include_object_default(obj, name, type_, reflected, compare_to):
    return True


def include_object_sqlite(obj, name, type_, reflected, compare_to):
    obj_schema = getattr(obj, "schema", None)
    log.info(
        f"include_object_sqlite: {name=}, {type_=}, {reflected=}, {compare_to=}, {obj_schema=}"
    )
    if obj_schema:
        log.warning(f"table {name} excluded since sqlite can not handle schemas")
        return False
    return True


def get_include_func(db_type: str):
    return {"sqlite": include_object_sqlite}.get(db_type, include_object_default)


def run_migrations_offline() -> None:
    # Use DSN from environment variable if available, otherwise fall back to config
    try:
        url = get_dsn_from_env()
    except ValueError:
        url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=False,
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
        dialect = connection.dialect.name
        if current_tenant:
            if dialect == "postgresql":
                # set search path on the connection, which ensures that
                # PostgreSQL will emit all CREATE / ALTER / DROP statements
                # in terms of this schema by default
                connection.execute(text(f'set search_path to "{current_tenant}"'))
                # in SQLAlchemy v2+ the search path change needs to be committed
                connection.commit()
            elif dialect in ("mysql", "mariadb"):
                # set "USE" on the connection, which ensures that
                # MySQL/MariaDB will emit all CREATE / ALTER / DROP statements
                # in terms of this schema by default

                connection.execute(text("USE %s" % current_tenant))

                # make use of non-supported SQLAlchemy attribute to ensure
                # the dialect reflects tables in terms of the current tenant name
            connection.dialect.default_schema_name = current_tenant

        configure_kwargs = {
            "include_schemas": False,
            # "version_table_schema": current_tenant,
            "include_object": get_include_func(dialect),
        }

        context.configure(
            connection=connection, target_metadata=target_metadata, **configure_kwargs
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
