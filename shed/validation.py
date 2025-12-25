"""Validation helpers and custom types for CLI."""

import typer

from .settings import DatabaseConfig


def validate_matching_db_types(src_db: DatabaseConfig, tgt_db: DatabaseConfig) -> None:
    """Validate that database types match."""
    src_type = src_db.connection.type
    tgt_type = tgt_db.connection.type
    if src_type != tgt_type:
        typer.secho(
            f"Error: Database types must match (source: {src_type}, target: {tgt_type})",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
