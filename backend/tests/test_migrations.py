from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, SQLModel

import app.db.models  # noqa: F401 — register all tables on SQLModel.metadata
from app.db import migrate as migrate_mod
from app.db.models import User
from app.db.session import _is_alembic_managed, init_db


def test_alembic_upgrade_creates_expected_schema(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "vault.sqlite"
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "alembic_version" in tables
    assert "models" in tables
    assert "files" in tables
    assert "print_jobs" in tables
    assert "refresh_tokens" in tables
    assert "printer_profiles" in tables
    assert "share_links" in tables

    files_columns = {col["name"]: col for col in inspector.get_columns("files")}
    assert "revision_label" in files_columns
    assert "revision_status" in files_columns
    assert "revision_notes" in files_columns
    assert "is_recommended" in files_columns
    assert files_columns["is_recommended"]["nullable"] is False
    assert files_columns["is_recommended"]["default"] is not None

    share_columns = {col["name"]: col for col in inspector.get_columns("share_links")}
    assert "model_id" in share_columns
    assert "token_hash" in share_columns
    assert "expires_at" in share_columns
    assert "allow_download" in share_columns
    assert "selected_file_ids_json" in share_columns


# --------------------------------------------------------------------------- #
# Strict coverage for the migration runner (app/db/migrate.py) and create_all
# gating — the entrypoint hardening for issue #29. Runs the real migration chain
# against temp SQLite *files* in every DB state the entrypoint must survive.
# --------------------------------------------------------------------------- #
def _url(tmp_path: Path, name: str = "runner.sqlite") -> str:
    return f"sqlite:///{tmp_path / name}"


def _head_revision() -> str:
    cfg = migrate_mod._alembic_config("sqlite://")
    head = ScriptDirectory.from_config(cfg).get_current_head()
    assert head is not None
    return head


def _current(url: str) -> str | None:
    engine = create_engine(url)
    try:
        return migrate_mod._current_revision(engine)
    finally:
        engine.dispose()


def _table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_runner_fresh_db_migrates_to_head_and_stamps(tmp_path: Path) -> None:
    url = _url(tmp_path)
    migrate_mod.run_migrations(url)

    assert _current(url) == _head_revision()
    assert {"users", "models", "files", "alembic_version"} <= _table_names(url)


def test_runner_is_idempotent_noop_at_head(tmp_path: Path) -> None:
    url = _url(tmp_path)
    migrate_mod.run_migrations(url)
    head = _current(url)
    migrate_mod.run_migrations(url)  # must not raise, must not move off head
    assert _current(url) == head == _head_revision()


def test_runner_orphan_db_is_adopted_without_table_exists_error(tmp_path: Path) -> None:
    # The issue #29 state: full schema built by create_all(), no alembic_version.
    url = _url(tmp_path)
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    assert _current(url) is None
    assert "users" in _table_names(url) and "alembic_version" not in _table_names(url)

    # A naive `upgrade head` would hit "table already exists"; the runner must
    # stamp first and finish cleanly at head.
    migrate_mod.run_migrations(url)
    assert _current(url) == _head_revision()


def test_runner_orphan_rescue_preserves_existing_data(tmp_path: Path) -> None:
    url = _url(tmp_path)
    engine = create_engine(url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            User(
                username="keepme",
                hashed_password="x",
                is_active=True,
                is_superuser=True,
            )
        )
        session.commit()
    engine.dispose()

    migrate_mod.run_migrations(url)

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            names = [r[0] for r in conn.execute(text("SELECT username FROM users"))]
    finally:
        engine.dispose()
    assert "keepme" in names  # rescue never dropped or rebuilt the data


def test_has_application_tables_ignores_alembic_only(tmp_path: Path) -> None:
    url = _url(tmp_path)
    engine = create_engine(url)
    try:
        assert migrate_mod._has_application_tables(engine) is False
    finally:
        engine.dispose()


def test_init_db_builds_schema_on_unmanaged_db(tmp_path: Path) -> None:
    url = _url(tmp_path, "init.sqlite")
    engine = create_engine(url)
    try:
        assert "users" not in set(inspect(engine).get_table_names())
        init_db(engine)
        assert "users" in set(inspect(engine).get_table_names())
        assert _is_alembic_managed(engine) is False  # create_all leaves it un-stamped
    finally:
        engine.dispose()


def test_init_db_is_strict_noop_on_alembic_managed_db(tmp_path: Path) -> None:
    url = _url(tmp_path, "managed.sqlite")
    migrate_mod.run_migrations(url)

    engine = create_engine(url)
    try:
        assert _is_alembic_managed(engine) is True
        before = set(inspect(engine).get_table_names())
        init_db(engine)  # must NOT call create_all
        assert set(inspect(engine).get_table_names()) == before
        assert migrate_mod._current_revision(engine) == _head_revision()
    finally:
        engine.dispose()
