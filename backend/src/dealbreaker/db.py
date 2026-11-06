"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

# SQLite needs check_same_thread=False when used across the scheduler + request threads.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def _migrate_columns(target_engine) -> None:
    """Ensure new optional columns exist on pre-existing tables without requiring Alembic."""
    inspector = inspect(target_engine)
    tables = set(inspector.get_table_names())
    migrations: list[tuple[str, str, str]] = [
        ("products", "search_query", "VARCHAR"),
        ("products", "category", "VARCHAR"),
        ("urls", "last_error", "VARCHAR"),
    ]
    with target_engine.begin() as conn:
        for table, column, col_type in migrations:
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


def init_db() -> None:
    # Import models so they register on SQLModel.metadata before create_all.
    from . import models  # noqa: F401
    from .stores import seed_default_stores

    SQLModel.metadata.create_all(engine)
    _migrate_columns(engine)
    with Session(engine) as session:
        seed_default_stores(session)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
