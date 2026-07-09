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
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import app.services.backup as backup
import app.services.storage_backend as storage_backend
from app.core.config import _overlay
from app.db.models import Document, DocumentKind, File, FileType, Model, User
from app.db.session import SQLiteSessionFactory, override_session_factory
from app.services.auth import create_access_token, hash_password
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
    # Real restores wait a grace period for in-flight jobs to finish; tests
    # don't need to pay that wall-clock cost.
    monkeypatch.setattr(backup, "_RESTORE_GRACE_PERIOD_S", 0)

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


def _seed_document_with_blob(env: BackupEnv, *, name: str, content: bytes) -> str:
    """Create a binary Document row and write its blob. Returns the storage key."""
    with env.new_session() as session:
        doc = Document(name=name, kind=DocumentKind.PDF)
        session.add(doc)
        session.commit()
        session.refresh(doc)
        key = get_backend().document_file_key(doc.id, name)
        get_backend().write_bytes(content, key)
        doc.filename = name
        doc.size_bytes = len(content)
        session.add(doc)
        session.commit()
        return key


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


def _auth_headers(env: BackupEnv) -> dict[str, str]:
    with env.new_session() as session:
        user = User(
            username="backup-admin",
            hashed_password=hash_password("Password123"),
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        token = create_access_token(user.id, user.username, scope="admin")
    return {"Authorization": f"Bearer {token}"}


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


def test_manifest_is_first_archive_member(backup_env: BackupEnv):
    """The manifest must be the first entry so listing (a streaming read) can
    stop after one small member instead of pulling the whole archive."""
    import gzip
    import tarfile

    _seed_model_with_blob(backup_env, name="Widget", content=b"solid widget\n")
    _seed_model_with_blob(backup_env, name="Gadget", content=b"solid gadget\n")
    meta = backup.create_backup()

    with gzip.open(Path(meta.path), "rb") as gz:
        with tarfile.open(fileobj=gz, mode="r|") as tar:
            first = next(iter(tar))
    assert first.name == "manifest.json"


def test_backup_appears_in_list_and_get(backup_env: BackupEnv):
    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    listed = backup.list_backups()
    assert any(m.id == meta.id for m in listed)

    fetched = backup.get_backup(meta.id)
    assert fetched is not None
    assert fetched.id == meta.id
    assert fetched.file_count == 1


def test_download_backup_archive_endpoint(client: TestClient, backup_env: BackupEnv):
    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    resp = client.get(
        f"/api/v1/backups/{meta.id}/download",
        headers=_auth_headers(backup_env),
    )

    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"\x1f\x8b")
    assert Path(meta.path).name in resp.headers["content-disposition"]


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


def test_backup_includes_document_blobs(backup_env: BackupEnv):
    """Documents are vault-owned bytes: a backup that omits them is a lie."""
    content = b"%PDF-1.4 assembly manual\n"
    key = _seed_document_with_blob(backup_env, name="manual.pdf", content=content)
    meta = backup.create_backup()

    Path(key).unlink()
    result = backup.restore_backup(meta.id)

    assert Path(key).exists(), "document blob was never in the archive"
    assert Path(key).read_bytes() == content
    assert result["restored_files"] == 1


def test_download_then_restore_endpoint_round_trip(
    client: TestClient, backup_env: BackupEnv
):
    content = b"solid endpoint widget\nendsolid\n"
    _model_id, key = _seed_model_with_blob(
        backup_env, name="Endpoint Widget", content=content
    )
    headers = _auth_headers(backup_env)

    create = client.post("/api/v1/backups", headers=headers)
    assert create.status_code == 202, create.text
    backup_id = create.json()["backup_id"]

    download = client.get(f"/api/v1/backups/{backup_id}/download", headers=headers)
    assert download.status_code == 200, download.text
    assert download.content.startswith(b"\x1f\x8b")
    assert f"{backup_id}.tar.gz" in download.headers["content-disposition"]

    # Disaster: remove both catalog row and stored bytes, then restore via API.
    with backup_env.new_session() as session:
        for m in session.exec(select(Model).where(Model.name == "Endpoint Widget")):
            session.delete(m)
        session.commit()
    Path(key).unlink()

    assert "Endpoint Widget" not in _read_model_names(backup_env)
    assert not Path(key).exists()

    restore = client.post(f"/api/v1/backups/{backup_id}/restore", headers=headers)
    assert restore.status_code == 200, restore.text
    assert restore.json() == {"backup_id": backup_id, "restored_files": 1}

    assert "Endpoint Widget" in _read_model_names(backup_env)
    assert Path(key).read_bytes() == content


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_restore_unknown_backup_raises(backup_env: BackupEnv):
    with pytest.raises(FileNotFoundError):
        backup.restore_backup("does-not-exist")


# ---------------------------------------------------------------------------
# Audit trail (0.8.5 item 3): backup/restore mutate the filesystem and swap
# the DB file, so they don't flow through the ORM after_flush hook — the
# service writes AuditLog rows explicitly.
# ---------------------------------------------------------------------------


def test_backup_writes_audit_row(backup_env: BackupEnv):
    from app.db.models import AuditLog

    backup.create_backup()

    with backup_env.new_session() as session:
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "backup.create")
        ).all()
    assert len(rows) == 1
    assert rows[0].resource_type == "backup"


def test_restore_writes_complete_row_on_success(backup_env: BackupEnv):
    from app.db.models import AuditLog

    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    backup.restore_backup(meta.id)

    # restore.start was written before the DB swap and lives only in the
    # pre-restore database, which no longer exists after a successful
    # restore — restore.complete is the persisted, post-swap signal.
    with backup_env.new_session() as session:
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "restore.complete")
        ).all()
    assert len(rows) == 1
    assert rows[0].resource_type == "backup"


def test_restore_rejected_while_job_running_writes_start_and_failed_rows(
    backup_env: BackupEnv,
):
    from app.db.models import AuditLog
    from app.services.jobs import registry

    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    job_id = registry.create()
    registry.update(job_id, state="running")
    try:
        with pytest.raises(backup.RestoreConflictError):
            backup.restore_backup(meta.id)
    finally:
        registry.update(job_id, state="completed")

    # No DB swap happened, so both rows survive in the current database.
    with backup_env.new_session() as session:
        actions = {row.action for row in session.exec(select(AuditLog)).all()}
    assert "restore.start" in actions
    assert "restore.failed" in actions


def test_failed_restore_writes_failed_row(
    backup_env: BackupEnv, monkeypatch: pytest.MonkeyPatch
):
    from app.db.models import AuditLog

    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure mid-restore")

    monkeypatch.setattr(backup, "_download_backup_to_local", _boom)

    with pytest.raises(RuntimeError):
        backup.restore_backup(meta.id)

    with backup_env.new_session() as session:
        actions = {row.action for row in session.exec(select(AuditLog)).all()}
    assert "restore.failed" in actions


# ---------------------------------------------------------------------------
# Restore gate (item 11: quiesce background loops during restore)
# ---------------------------------------------------------------------------


def test_restore_rejected_while_job_running(backup_env: BackupEnv):
    from app.services.jobs import registry

    model_id, _key = _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    job_id = registry.create()
    registry.update(job_id, state="running")
    try:
        with pytest.raises(backup.RestoreConflictError):
            backup.restore_backup(meta.id)
    finally:
        registry.update(job_id, state="completed")

    assert not backup.restore_in_progress()
    with backup_env.new_session() as session:
        assert session.get(Model, model_id) is not None


def test_gc_skips_during_restore(backup_env: BackupEnv):
    from app.services import trash

    # A trashed row past retention would normally be purged.
    with backup_env.new_session() as session:
        from app.core.time import utcnow
        from datetime import timedelta

        from app.db.models import Tag

        session.add(Tag(name="stale", slug="stale", deleted_at=utcnow() - timedelta(days=999)))
        session.commit()

    backup._restore_gate.set()
    try:
        result = trash.gc_soft_deleted()
    finally:
        backup._restore_gate.clear()

    assert result == {"rows": 0, "orphan_blobs": 0}
    with backup_env.new_session() as session:
        assert session.exec(select(Tag)).first() is not None


def test_gate_is_cleared_when_restore_raises(
    backup_env: BackupEnv, monkeypatch: pytest.MonkeyPatch
):
    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure mid-restore")

    monkeypatch.setattr(backup, "_download_backup_to_local", _boom)

    with pytest.raises(RuntimeError):
        backup.restore_backup(meta.id)

    assert not backup.restore_in_progress()


def test_delete_backup_removes_archive(backup_env: BackupEnv):
    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()
    assert Path(meta.path).exists()

    assert backup.delete_backup(meta.id) is True
    assert not Path(meta.path).exists()
    assert backup.get_backup(meta.id) is None


def test_delete_unknown_backup_returns_false(backup_env: BackupEnv):
    assert backup.delete_backup("nope") is False


def test_backup_id_round_trips_despite_timestamped_name(backup_env: BackupEnv):
    """The archive name embeds a hyphenated timestamp before the id; the id
    derived on list/get must still equal the one create_backup returned
    (regression for the rsplit-based id extraction)."""
    _seed_model_with_blob(backup_env, name="Widget", content=b"x")
    meta = backup.create_backup()

    # id is the trailing 12-hex token, not a timestamp fragment.
    assert len(meta.id) == 12
    assert all(c in "0123456789abcdef" for c in meta.id)
    assert f"-{meta.id}.tar.gz" in Path(meta.path).name

    fetched = backup.get_backup(meta.id)
    assert fetched is not None and fetched.id == meta.id


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
