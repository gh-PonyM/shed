"""Test models for migration testing."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model for testing."""

    id: int | None = Field(default=None, primary_key=True)
    name: str


class Post(SQLModel, table=True):
    """Post model for testing."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id")


class Flight(SQLModel, table=True):
    """Post model for testing."""

    # Such a model is always included in migrations. The query engine would always
    # use this schema independent of the search_path in postgres. This is an edge-case.
    __table_args__ = {"schema": "aviation"}
    id: int | None = Field(default=None, primary_key=True)
    time: datetime
