"""Feature #3 — a 3MF's embedded project/plate image must win over the bare
mesh render as the model thumbnail.

Regression guard for the ``persist_artifact`` ``overwrite_thumbnail`` clobber:
``_3mf_extract_docs_and_plates`` sets ``model.thumbnail_file_id`` to a plate
IMAGE during extraction, but the subsequent mesh-render ``persist_artifact``
(``overwrite_thumbnail=True``) used to overwrite it with the grey mesh render.

Driven by the real multi-plate fixture when present; skips otherwise.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import _overlay
from app.db.models import File, FileType, Model
from app.services.ingestion import ingest_mesh
from app.services.jobs import registry

TESTDATA = Path(__file__).resolve().parents[2] / "testdata"
# Real BambuStudio export: 2 plates (3DBenchy, Torus), embedded plate_*.png
# renders and Auxiliaries/Model Pictures/*.png project photos.
MULTIPLATE_3MF = TESTDATA / "multiplate_2plates_benchy_torus.3mf"


def _requires(path: Path):
    return pytest.mark.skipif(not path.exists(), reason=f"missing real fixture {path}")


def _configure_storage(tmp_path: Path) -> None:
    _overlay["data_dir"] = tmp_path / "files"
    _overlay["thumb_dir"] = tmp_path / "thumbs"
    _overlay["staging_dir"] = tmp_path / "staging"
    (tmp_path / "files").mkdir(parents=True, exist_ok=True)
    (tmp_path / "thumbs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "staging" / "_incoming").mkdir(parents=True, exist_ok=True)


def _stage_copy(src: Path) -> Path:
    staged = Path(_overlay["staging_dir"]) / "_incoming" / f"{uuid.uuid4().hex}-{src.name}"
    shutil.copy(src, staged)
    return staged


def _ingest_mesh(
    session: Session, src: Path, file_type: FileType, *, model_name: str
) -> tuple[Model, File]:
    job_id = registry.create()
    ingest_mesh(
        job_id=job_id,
        staged_path=_stage_copy(src),
        original_filename=src.name,
        model_name=model_name,
        file_type=file_type,
        collection="Test Plates",
        tags=None,
        source_hash=None,
    )
    job = registry.get(job_id)
    assert job is not None and job.state == "completed", getattr(job, "error", None)
    session.expire_all()
    return session.get(Model, job.model_id), session.get(File, job.file_id)


@_requires(MULTIPLATE_3MF)
def test_3mf_plate_image_wins_over_mesh_render(
    tmp_path: Path, db_session: Session
) -> None:
    _configure_storage(tmp_path)
    model, mesh_file = _ingest_mesh(
        db_session, MULTIPLATE_3MF, FileType.THREE_MF, model_name="Multiplate Test"
    )

    assert model.thumbnail_file_id is not None
    thumb_file = db_session.get(File, model.thumbnail_file_id)
    assert thumb_file is not None
    # The catalog thumbnail must be the extracted plate IMAGE, not the 3MF mesh
    # render (which would clobber the slicer preview the user actually saw).
    assert thumb_file.file_type == FileType.IMAGE, (
        f"expected an IMAGE thumbnail (3MF plate render), got "
        f"{thumb_file.file_type} ({thumb_file.original_filename})"
    )
    assert thumb_file.id != mesh_file.id


@_requires(MULTIPLATE_3MF)
def test_3mf_extracts_plate_images_as_files(
    tmp_path: Path, db_session: Session
) -> None:
    """The plate renders land as IMAGE File rows under the model."""
    _configure_storage(tmp_path)
    model, _ = _ingest_mesh(
        db_session, MULTIPLATE_3MF, FileType.THREE_MF, model_name="Multiplate Images"
    )
    images = db_session.exec(
        select(File).where(
            File.model_id == model.id, File.file_type == FileType.IMAGE
        )
    ).all()
    assert images, "expected extracted plate/project images as IMAGE files"
    names = {img.original_filename for img in images}
    # At least the per-plate slicer renders should be present.
    assert any(n.startswith("plate_") for n in names), names
