from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import _overlay
from app.db.models import File, FileType, Metadata, Model, User
from app.services import library_transfer


def _seed(db: Session, tmp_path: Path) -> tuple[User, Model, File]:
    _overlay["data_dir"] = tmp_path / "files"
    _overlay["thumb_dir"] = tmp_path / "thumbs"
    user = db.exec(select(User)).first()
    assert user is not None
    model = Model(name="Calibration cube", slug="calibration-cube", hash="a" * 64)
    db.add(model)
    db.commit()
    db.refresh(model)
    blob = tmp_path / "files" / "calibration-cube" / "v1" / "cube.stl"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"solid cube\nendsolid cube\n")
    import hashlib

    file_row = File(
        model_id=model.id,
        path=str(blob),
        original_filename="cube.stl",
        file_type=FileType.STL,
        version=1,
        size_bytes=blob.stat().st_size,
        sha256=hashlib.sha256(blob.read_bytes()).hexdigest(),
    )
    db.add(file_row)
    db.commit()
    db.refresh(file_row)
    db.add(Metadata(file_id=file_row.id, bbox_x_mm=20, bbox_y_mm=20, bbox_z_mm=20))
    db.commit()
    return user, model, file_row


def test_library_archive_manifest_blobs_and_idempotent_import(
    db_session: Session, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    user, _, file_row = _seed(db_session, tmp_path)
    archive_path = library_transfer.create_archive(db_session, user)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["format"] == "printstash-library-v1"
            artifact = manifest["models"][0]["artifacts"][0]
            assert artifact["sha256"] == file_row.sha256
            assert archive.read(artifact["entry"]) == Path(file_row.path).read_bytes()
        result = library_transfer.import_archive(db_session, archive_path, user)
        assert result == {
            "created_models": 0,
            "created_files": 0,
            "skipped_files": 1,
            "imported_jobs": 0,
        }
    finally:
        archive_path.unlink(missing_ok=True)


def test_library_import_rejects_corrupt_blob(
    db_session: Session, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    user, _, _ = _seed(db_session, tmp_path)
    source = library_transfer.create_archive(db_session, user)
    corrupt = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(corrupt, "w") as output:
        for info in original.infolist():
            data = original.read(info.filename)
            output.writestr(
                info, b"corrupt" if info.filename.startswith("blobs/") else data
            )
    with pytest.raises(ValueError, match="archive_blob_hash_mismatch"):
        library_transfer.import_archive(db_session, corrupt, user)
    source.unlink(missing_ok=True)


def test_library_archive_api_downloads_zip(
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    _seed(db_session, tmp_path)
    response = client.get("/api/v1/models/library-archive", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    downloaded = tmp_path / "download.zip"
    downloaded.write_bytes(response.content)
    with zipfile.ZipFile(downloaded) as archive:
        assert json.loads(archive.read("manifest.json"))["format"] == "printstash-library-v1"
