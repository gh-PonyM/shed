"""Validation helpers and custom types for CLI."""

import typer

from .settings import DatabaseConfig


def validate_matching_db_types(src_db: DatabaseConfig, tgt_db: DatabaseConfig) -> None:
    """Validate that database types match."""
    if src_db.type != tgt_db.type:
        typer.secho(
            f"Error: Database types must match (source: {src_db.type}, target: {tgt_db.type})",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
