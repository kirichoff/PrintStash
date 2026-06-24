"""Database migration runner — the single, safe entry point for bringing a
database up to the latest Alembic revision.

Used by the container entrypoint (``python -m app.db.migrate``) so migrations run
on every start, however the app is launched, instead of depending on a fragile
Compose ``command:`` line (issue #29). Idempotent: a no-op when already at head.

It also **self-heals an "orphan" database** — one whose schema was built by the
app's startup ``create_all()`` without ever recording an Alembic version (what
happened when a user removed the Compose migration step). Running ``upgrade head``
on such a DB would fail with "table already exists" because the baseline
migration tries to re-create existing tables. So if we find application tables
but no ``alembic_version``, we ``stamp head`` first to adopt the existing schema,
then upgrade. ``stamp`` only writes the version marker — it touches no data.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# backend/app/db/migrate.py -> parents[2] == backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_SCRIPT_LOCATION = _BACKEND_DIR / "alembic"


def _alembic_config(url: str) -> Config:
    """Build an Alembic config programmatically (no alembic.ini file).

    Using ``Config()`` rather than ``Config("alembic.ini")`` leaves
    ``config_file_name`` as ``None``, which makes ``env.py`` skip ``fileConfig`` —
    so running migrations does not hijack the app/pytest logging configuration.
    """
    cfg = Config()
    cfg.set_main_option("script_location", str(_SCRIPT_LOCATION))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _current_revision(engine) -> str | None:
    """The DB's recorded Alembic revision, or None when it has never been stamped."""
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _has_application_tables(engine) -> bool:
    """True if the DB holds tables other than Alembic's own bookkeeping table."""
    tables = set(inspect(engine).get_table_names())
    tables.discard("alembic_version")
    return bool(tables)


def _create_all(url: str) -> None:
    """Build the full current schema directly from the SQLModel models."""
    import app.db.models  # noqa: F401 — register all tables on SQLModel.metadata

    engine = create_engine(url)
    try:
        SQLModel.metadata.create_all(engine)
    finally:
        engine.dispose()


def run_migrations(database_url: str | None = None) -> None:
    """Bring *database_url* (default: configured DB) to the latest revision.

    Handles all three states the entrypoint can meet:

    * **already managed** (has ``alembic_version``): applies any pending
      migrations; a no-op when already at head.
    * **orphan** (app tables but no ``alembic_version``): stamps head to adopt the
      existing schema, then upgrades — no data touched, no "table exists" error.
    * **fresh** (no tables): builds the schema directly from the models and stamps
      head, rather than replaying the historical migration chain. That chain was
      authored against SQLite and does not apply cleanly on stricter engines like
      Postgres (its baseline fails outright); on an empty database the chain's
      data backfills are no-ops, so ``create_all`` + ``stamp head`` yields an
      equivalent, head-stamped schema on every supported engine.
    """
    url = database_url or settings.db_url

    engine = create_engine(url)
    try:
        revision = _current_revision(engine)
        has_tables = _has_application_tables(engine)
    finally:
        engine.dispose()

    cfg = _alembic_config(url)

    if revision is not None:
        # Already managed by Alembic — apply any pending migrations.
        command.upgrade(cfg, "head")
    elif has_tables:
        # Orphan: schema built without recording a version (issue #29).
        logger.warning(
            "migrate: database has tables but no Alembic version — stamping head "
            "to adopt the existing schema before upgrading (orphan rescue). This "
            "writes only the version marker; no data is changed."
        )
        command.stamp(cfg, "head")
        command.upgrade(cfg, "head")
    else:
        # Fresh database — create the schema from the models, then stamp head so
        # Alembic considers it current (engine-agnostic; avoids the SQLite-only
        # baseline migration). Future migrations apply normally from here.
        logger.info(
            "migrate: empty database — creating schema from models and stamping head"
        )
        _create_all(url)
        command.stamp(cfg, "head")

    logger.info("migrate: database is at the latest revision (head)")


def main() -> None:  # pragma: no cover - thin CLI wrapper, exercised via entrypoint
    run_migrations()


if __name__ == "__main__":  # pragma: no cover
    main()
