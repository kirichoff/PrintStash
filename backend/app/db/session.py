from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator, Iterator, Protocol, runtime_checkable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# `check_same_thread=False` is required for SQLite + FastAPI (multiple threads).
_connect_args = (
    {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
)

_engine: Engine = create_engine(
    settings.db_url,
    echo=False,
    connect_args=_connect_args,
)


# ---------------------------------------------------------------------------
# SessionFactory Protocol & ContextVar — single seam for all session access
# See ADR-0001.
# ---------------------------------------------------------------------------


@runtime_checkable
class SessionFactory(Protocol):
    """Protocol for session factories — the single seam for DB session access.

    Two lifecycle patterns:
    - ``session()`` returns a raw Session — caller owns commit/close (background tasks).
    - ``scoped_session()`` returns a context manager — auto-closes on exit (FastAPI deps, ingestion).

    ``async_session()`` is a placeholder for Stage 4 Postgres.
    """

    def session(self) -> Session: ...
    def async_session(self) -> Any: ...
    def scoped_session(self) -> Generator[Session, None, None]: ...


class SQLiteSessionFactory:
    """Default production adapter: SQLModel sessions from the module-level engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def session(self) -> Session:
        return Session(self._engine)

    def async_session(self) -> Any:
        raise NotImplementedError("AsyncSession requires Postgres (Stage 4)")

    @contextmanager
    def scoped_session(self) -> Generator[Session, None, None]:
        session = Session(self._engine)
        try:
            yield session
        finally:
            session.close()


_factory_ctx: ContextVar[SessionFactory] = ContextVar(
    "session_factory",
    default=SQLiteSessionFactory(_engine),
)


def get_session_factory() -> SessionFactory:
    """Return the active SessionFactory from the context.

    Used by FastAPI dependencies and callers that need to create sessions
    without coupling to the module-level engine.  Tests override via
    ``override_session_factory()``, not monkeypatching.
    """
    return _factory_ctx.get()


def override_session_factory(factory: SessionFactory) -> None:
    """Override the ContextVar for testing. Restore after test teardown."""
    _factory_ctx.set(factory)


def get_engine() -> Engine:
    """Return the module-level engine. Only for low-level operations (backup restore, disposal)."""
    return _engine


# ---------------------------------------------------------------------------
# Mini-migrations: SQLite + create_all() never adds columns to existing tables.
# Until Stage 4 (Alembic), we hand-add new columns idempotently here.
# ---------------------------------------------------------------------------

_COLUMN_PATCHES: dict[str, list[tuple[str, str]]] = {
    "models": [
        ("category_id", "INTEGER"),
        ("thumbnail_file_id", "INTEGER"),
    ],
    "printers": [
        ("group", "VARCHAR(128)"),
    ],
    "print_jobs": [
        ("source", "VARCHAR(16) DEFAULT 'vault'"),
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
    insp = inspect(_engine)
    with _engine.begin() as conn:
        for table, cols in _COLUMN_PATCHES.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    logger.info("migrate: adding column %s.%s", table, name)
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN "{name}" {ddl}'))


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(_engine)
    _apply_column_patches()
    _ensure_sentinel_rows()


def _ensure_sentinel_rows() -> None:
    """Create sentinel Model + File rows used by external (non-vault) print jobs."""
    from app.db.models import File, FileType, Model, SENTINEL_MODEL_HASH, SENTINEL_FILE_HASH

    with Session(_engine) as session:
        sentinel_model = session.exec(
            select(Model).where(Model.hash == SENTINEL_MODEL_HASH)
        ).first()
        if sentinel_model is None:
            sentinel_model = Model(
                name="__external__",
                slug="__external__",
                hash=SENTINEL_MODEL_HASH,
            )
            session.add(sentinel_model)
            session.commit()
            session.refresh(sentinel_model)

        sentinel_file = session.exec(
            select(File).where(File.sha256 == SENTINEL_FILE_HASH)
        ).first()
        if sentinel_file is None:
            sentinel_file = File(
                model_id=sentinel_model.id,
                path="/dev/null",
                original_filename="__external__",
                file_type=FileType.GCODE,
                version=1,
                size_bytes=0,
                sha256=SENTINEL_FILE_HASH,
            )
            session.add(sentinel_file)
            session.commit()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a scoped Session and ensures cleanup."""
    factory = _factory_ctx.get()
    with factory.scoped_session() as session:
        yield session
