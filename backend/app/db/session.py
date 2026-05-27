from __future__ import annotations

from typing import Callable, Iterator

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# `check_same_thread=False` is required for SQLite + FastAPI (multiple threads).
_connect_args = (
    {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
)

engine: Engine = create_engine(
    settings.db_url,
    echo=False,
    connect_args=_connect_args,
)


SessionFactory = Callable[[], Session]
"""Type alias for a session factory suitable for background tasks + test injection."""


# Mini-migrations: SQLite + create_all() never adds columns to existing tables.
# Until Stage 4 (Alembic), we hand-add new columns idempotently here.
_COLUMN_PATCHES: dict[str, list[tuple[str, str]]] = {
    "models": [
        ("category_id", "INTEGER"),
        ("thumbnail_file_id", "INTEGER"),
    ],
    "system_config": [
        ("storage_backend", "VARCHAR(64)"),
        ("s3_bucket", "VARCHAR(256)"),
        ("s3_endpoint_url", "VARCHAR(512)"),
        ("s3_region", "VARCHAR(128)"),
        ("s3_access_key", "VARCHAR(256)"),
        ("s3_secret_key", "VARCHAR(512)"),
        ("backup_retention_days", "INTEGER"),
        ("backup_s3_bucket", "VARCHAR(256)"),
        ("backup_s3_endpoint_url", "VARCHAR(512)"),
        ("backup_s3_region", "VARCHAR(128)"),
        ("backup_s3_access_key", "VARCHAR(256)"),
        ("backup_s3_secret_key", "VARCHAR(512)"),
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


def get_session_factory() -> SessionFactory:
    """FastAPI dependency: returns a session factory for background tasks.

    Callers get a simple callable so they can create their own sessions
    without coupling to the module-level engine.  Tests can override this
    dependency to inject an in-memory SQLite factory.
    """
    return lambda: Session(engine)
