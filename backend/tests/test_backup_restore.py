"""Backup & restore round-trip tests.

These exercise the local-storage backup path end to end: create an archive
from a populated vault (DB + blobs), then prove a restore brings the database
rows and the stored file bytes back after a simulated disaster.

The shared in-memory test harness can't be used here: ``create_backup`` reads
the SQLite database *as a file* (``_backup_sqlite_copy``) and ``_restore_database``
writes the file back, so these tests stand up a self-contained file-based DB and
a local storage root under ``tmp_path``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import app.services.backup as backup
import app.services.storage_backend as storage_backend
from app.core.config import _overlay
from app.db.models import File, FileType, Model
from app.db.session import SQLiteSessionFactory, override_session_factory
from app.services.storage_backend import get_backend


@dataclass
class BackupEnv:
    root: Path
    data_dir: Path
    backup_dir: Path
    db_file: Path
    engine: object

    def new_session(self) -> Session:
        return Session(self.engine)


@pytest.fixture
def backup_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[BackupEnv]:
    data_dir = tmp_path / "files"
    thumb_dir = tmp_path / "thumbs"
    backup_dir = tmp_path / "backups"
    db_dir = tmp_path / "db"
    for d in (data_dir, thumb_dir, backup_dir, db_dir):
        d.mkdir(parents=True, exist_ok=True)
    db_file = db_dir / "vault.sqlite"
    db_url = f"sqlite:///{db_file}"

    # Point the effective config at our file-based vault.
    _overlay.update(
        {
            "storage_backend": "local",
            "data_dir": data_dir,
            "thumb_dir": thumb_dir,
            "backup_dir": backup_dir,
            "db_url": db_url,
        }
    )

    # A real on-disk SQLite DB that the session factory and the backup
    # service's file-level reads/writes both target.
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    override_session_factory(SQLiteSessionFactory(engine))

    # Reset cached singletons so they pick up our overlay.
    monkeypatch.setattr(storage_backend, "_backend", None, raising=False)
    monkeypatch.setattr(backup, "_backup_s3", None, raising=False)

    try:
        yield BackupEnv(
            root=tmp_path,
            data_dir=data_dir,
            backup_dir=backup_dir,
            db_file=db_file,
            engine=engine,
        )
    finally:
        engine.dispose()


def _seed_model_with_blob(
    env: BackupEnv, *, name: str, content: bytes
) -> tuple[int, str]:
    """Create a Model + File row and write the blob through the backend.

    Returns ``(model_id, storage_key)``.
    """
    slug = name.lower().replace(" ", "-")
    key = get_backend().blob_key(slug, 1, f"{slug}.stl")
    get_backend().write_bytes(content, key)

    sha = hashlib.sha256(content).hexdigest()
    with env.new_session() as session:
        model = Model(name=name, slug=slug, hash=sha)
        session.add(model)
        session.commit()
        session.refresh(model)
        f = File(
            model_id=model.id,
            path=key,
            original_filename=f"{slug}.stl",
            file_type=FileType.STL,
            version=1,
            size_bytes=len(content),
            sha256=sha,
        )
        session.add(f)
        session.commit()
        return model.id, key


def _read_model_names(env: BackupEnv) -> list[str]:
    """Read model names through a brand-new engine so the restored DB file is
    seen, not a connection cached against the pre-restore file."""
    eng = create_engine(
        f"sqlite:///{env.db_file}", connect_args={"check_same_thread": False}
    )
    try:
        with Session(eng) as session:
            return [m.name for m in session.exec(select(Model)).all()]
    finally:
        eng.dispose()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_backup_archive_contents(backup_env: BackupEnv):
    _seed_model_with_blob(backup_env, name="Widget", content=b"solid widget\n")
    _seed_model_with_blob(backup_env, name="Gadget", content=b"solid gadget\n")

    meta = backup.create_backup()

    assert meta.file_count == 2
    assert meta.location == "local"
    archive = Path(meta.path)
    assert archive.exists() and archive.stat().st_size > 0
    assert meta.size_bytes == archive.stat().st_size

    import gzip
    import tarfile

    names = set()
    with gzip.open(archive, "rb") as gz:
        with tarfile.open(fileobj=gz, mode="r|") as tar:
            for member in tar:
                names.add(member.name)

    assert "db.sqlite3" in names
    assert "manifest.json" in names
    # Two blobs captured under files/.
    assert sum(1 for n in names if n.startswith("files/") and n != "files/") == 2


def test_backup_appears_in_list_and_get(backup_env: BackupEnv):
    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    listed = backup.list_backups()
    assert any(m.id == meta.id for m in listed)

    fetched = backup.get_backup(meta.id)
    assert fetched is not None
    assert fetched.id == meta.id
    assert fetched.file_count == 1


# ---------------------------------------------------------------------------
# Restore round trip
# ---------------------------------------------------------------------------


def test_restore_recovers_database_rows(backup_env: BackupEnv):
    _seed_model_with_blob(backup_env, name="Widget", content=b"solid widget\n")
    meta = backup.create_backup()

    # Disaster: wipe every model row.
    with backup_env.new_session() as session:
        for m in session.exec(select(Model)).all():
            session.delete(m)
        session.commit()
    backup_env.engine.dispose()

    assert _read_model_names(backup_env) == []

    backup.restore_backup(meta.id)

    assert "Widget" in _read_model_names(backup_env)


def test_restore_recovers_blob_bytes(backup_env: BackupEnv):
    content = b"solid widget\nendsolid\n"
    _model_id, key = _seed_model_with_blob(backup_env, name="Widget", content=content)
    meta = backup.create_backup()

    # Disaster: delete the stored blob.
    Path(key).unlink()
    assert not Path(key).exists()

    result = backup.restore_backup(meta.id)

    assert result["restored_files"] == 1
    # The blob the database references must be back, byte-for-byte.
    assert Path(key).exists(), "restored blob is missing at its storage key"
    assert Path(key).read_bytes() == content


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_restore_unknown_backup_raises(backup_env: BackupEnv):
    with pytest.raises(FileNotFoundError):
        backup.restore_backup("does-not-exist")


def test_delete_backup_removes_archive(backup_env: BackupEnv):
    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()
    assert Path(meta.path).exists()

    assert backup.delete_backup(meta.id) is True
    assert not Path(meta.path).exists()
    assert backup.get_backup(meta.id) is None


def test_delete_unknown_backup_returns_false(backup_env: BackupEnv):
    assert backup.delete_backup("nope") is False


def test_purge_keeps_fresh_removes_old(
    backup_env: BackupEnv, monkeypatch: pytest.MonkeyPatch
):
    from datetime import timedelta

    from app.core.time import utcnow

    # An old backup: pin create_backup's clock 60 days into the past.
    monkeypatch.setattr(backup, "utcnow", lambda: utcnow() - timedelta(days=60))
    old = backup.create_backup()

    # A fresh backup at the real clock.
    monkeypatch.setattr(backup, "utcnow", utcnow)
    fresh = backup.create_backup()

    removed = backup.purge_old_backups(retain_days=30)

    assert removed == 1
    remaining = {m.id for m in backup.list_backups()}
    assert old.id not in remaining
    assert fresh.id in remaining
