from __future__ import annotations

from typing import Iterator

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# `check_same_thread=False` is required for SQLite + FastAPI (multiple threads).
_connect_args = {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}

engine: Engine = create_engine(
    settings.db_url,
    echo=False,
    connect_args=_connect_args,
)


# Mini-migrations: SQLite + create_all() never adds columns to existing tables.
# Until Stage 4 (Alembic), we hand-add new columns idempotently here.
_COLUMN_PATCHES: dict[str, list[tuple[str, str]]] = {
    "models": [
        ("category_id", "INTEGER"),
        ("thumbnail_file_id", "INTEGER"),
    ],
}


def _apply_column_patches() -> None:
    if not settings.db_url.startswith("sqlite"):
        return
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _COLUMN_PATCHES.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    logger.info("migrate: adding column %s.%s", table, name)
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Importing models registers them with SQLModel.metadata.
    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _apply_column_patches()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a Session and ensures cleanup."""
    with Session(engine) as session:
        yield session
