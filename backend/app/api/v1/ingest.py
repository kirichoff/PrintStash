from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File as UploadFileParam,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import require_api_key
from app.db.session import SessionFactory, get_session_factory
from app.schemas.ingest import IngestJobStatus, IngestResponse
from app.services import storage
from app.services.ingestion import ingest_mesh, ingest_orca_gcode
from app.services.jobs import registry

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _stage_upload(upload: UploadFile, suffix: str) -> Path:
    """Stream an UploadFile into the staging directory; return the staged path."""
    staged = settings.incoming_dir / f"{uuid.uuid4().hex}{suffix}"
    written = storage.stream_to_path(upload.file, staged)
    if written > settings.max_upload_bytes:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="upload_too_large",
        )
    return staged


@router.post(
    "/orca",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
    summary="Ingest a sliced G-code file from OrcaSlicer",
    description=(
        "Multipart upload from the OrcaSlicer post-processing hook. The G-code is "
        "staged immediately and processed asynchronously: hashed, parsed for slicer "
        "metadata, thumbnail-extracted, deduplicated, and persisted. Returns a "
        "job_id you can poll via GET /ingest/jobs/{job_id}."
    ),
)
async def ingest_orca(
    background_tasks: BackgroundTasks,
    file: UploadFile = UploadFileParam(..., description="The .gcode file"),
    model_name: Optional[str] = Form(None, description="Display name for the model"),
    category: Optional[str] = Form(
        None, description="Optional category, e.g. 'Functional/Brackets'"
    ),
    tags: Optional[str] = Form(None, description="Comma-separated tag list"),
    source_hash: Optional[str] = Form(
        None, description="Optional sha256 of the source mesh for dedup"
    ),
    session_factory: SessionFactory = Depends(get_session_factory),
) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename_required")

    original_filename = Path(file.filename).name
    suffix = Path(original_filename).suffix.lower() or ".gcode"

    if suffix not in {".gcode", ".g", ".gco"}:
        raise HTTPException(status_code=400, detail="unsupported_file_type")

    staged = _stage_upload(file, suffix)
    name = (model_name or Path(original_filename).stem).strip() or Path(
        original_filename
    ).stem

    job_id = registry.create()
    background_tasks.add_task(
        ingest_orca_gcode,
        job_id=job_id,
        staged_path=staged,
        original_filename=original_filename,
        model_name=name,
        category=category,
        tags=tags,
        source_hash=source_hash,
        session_factory=session_factory,
    )

    return IngestResponse(job_id=job_id, state="pending")


@router.get(
    "/jobs/{job_id}",
    response_model=IngestJobStatus,
    summary="Get the status of an ingestion job",
)
def get_job(job_id: str) -> IngestJobStatus:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job


_MESH_SUFFIXES = {".stl", ".3mf", ".obj"}
_SUFFIX_TO_TYPE = {
    ".stl": "stl",
    ".3mf": "3mf",
    ".obj": "obj",
}


@router.post(
    "/model",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
    summary="Ingest a source mesh file (STL, 3MF, OBJ)",
    description=(
        "Multipart upload of a source mesh. The file is staged and processed "
        "asynchronously: hashed, geometry extracted via trimesh (bounding box, "
        "volume, triangle count), a PNG thumbnail rendered, deduplicated, and "
        "persisted. Returns a job_id you can poll via GET /ingest/jobs/{job_id}."
    ),
)
async def ingest_model(
    background_tasks: BackgroundTasks,
    file: UploadFile = UploadFileParam(..., description="The .stl, .3mf, or .obj file"),
    model_name: Optional[str] = Form(None, description="Display name for the model"),
    category: Optional[str] = Form(
        None, description="Optional category, e.g. 'Functional/Brackets'"
    ),
    tags: Optional[str] = Form(None, description="Comma-separated tag list"),
    source_hash: Optional[str] = Form(None, description="Optional sha256 for dedup"),
    session_factory: SessionFactory = Depends(get_session_factory),
) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename_required")

    original_filename = Path(file.filename).name
    suffix = Path(original_filename).suffix.lower()

    if suffix not in _MESH_SUFFIXES:
        raise HTTPException(status_code=400, detail="unsupported_file_type")

    staged = _stage_upload(file, suffix)
    name = (model_name or Path(original_filename).stem).strip() or Path(
        original_filename
    ).stem

    from app.db.models import FileType

    file_type_map = {
        ".stl": FileType.STL,
        ".3mf": FileType.THREE_MF,
        ".obj": FileType.OBJ,
    }

    job_id = registry.create()
    background_tasks.add_task(
        ingest_mesh,
        job_id=job_id,
        staged_path=staged,
        original_filename=original_filename,
        model_name=name,
        category=category,
        tags=tags,
        file_type=file_type_map[suffix],
        source_hash=source_hash,
        session_factory=session_factory,
    )

    return IngestResponse(job_id=job_id, state="pending")
