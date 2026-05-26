"""File download + thumbnail + on-the-fly STL conversion."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, select

from app.core.http import get_or_404
from app.core.logging import get_logger
from app.core.security import require_auth
from app.db.models import File, FileType, Model
from app.db.session import get_session
from app.services import storage

logger = get_logger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

_MESH_TYPES = {FileType.STL, FileType.THREE_MF, FileType.OBJ}


@router.get(
    "/{file_id}/download",
    summary="Download the raw file blob",
    description="Streams the underlying artifact (G-code/STL/3MF/OBJ) from disk.",
)
def download_file(file_id: int, session: Session = Depends(get_session)) -> FileResponse:
    f = get_or_404(session, File, file_id, "file_not_found")
    path = Path(f.path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="file_blob_missing")
    return FileResponse(
        path=str(path),
        filename=f.original_filename,
        media_type="application/octet-stream",
    )


@router.get(
    "/{file_id}/thumbnail",
    summary="Get the PNG thumbnail extracted from the file (if any)",
)
def file_thumbnail(file_id: int, session: Session = Depends(get_session)) -> FileResponse:
    get_or_404(session, File, file_id, "file_not_found")
    thumb = storage.thumbnail_path_for(file_id)
    if not thumb.exists():
        raise HTTPException(status_code=404, detail="thumbnail_not_found")
    return FileResponse(path=str(thumb), media_type="image/png")


@router.get(
    "/{file_id}/stl",
    summary="Serve any mesh file as STL for 3D preview",
    description=(
        "If the file is already STL it is served directly. 3MF and OBJ files are "
        "converted to binary STL on the fly via trimesh."
    ),
)
def file_as_stl(file_id: int, session: Session = Depends(get_session)) -> StreamingResponse:
    # Lazy import: trimesh is heavy; pulling it in only for endpoints that need it.
    from app.services import mesh_processing

    f = get_or_404(session, File, file_id, "file_not_found")
    path = Path(f.path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="file_blob_missing")

    if path.suffix.lower() == ".stl":
        return FileResponse(
            path=str(path),
            filename=f.original_filename,
            media_type="application/sla",
        )

    stl_bytes = mesh_processing.to_stl_bytes(path)
    if stl_bytes is None:
        raise HTTPException(status_code=500, detail="stl_conversion_failed")

    stem = Path(f.original_filename).stem
    return StreamingResponse(
        io.BytesIO(stl_bytes),
        media_type="application/sla",
        headers={"Content-Disposition": f'attachment; filename="{stem}.stl"'},
    )


@router.post(
    "/thumbnails/rebuild",
    dependencies=[Depends(require_auth)],
    summary="Regenerate missing mesh thumbnails for existing models",
    description=(
        "Walks every non-soft-deleted Model that has no thumbnail and tries to "
        "render one from its newest mesh file (STL/3MF/OBJ). Useful after a "
        "dependency fix (e.g. installing networkx for 3MF parsing) without "
        "re-uploading. Returns a per-model summary."
    ),
)
def rebuild_missing_thumbnails(
    session: Session = Depends(get_session),
) -> dict:
    from app.services import mesh_processing

    models = session.exec(
        select(Model).where(
            Model.deleted_at.is_(None),  # type: ignore[union-attr]
            Model.thumbnail_file_id.is_(None),  # type: ignore[union-attr]
        )
    ).all()

    rebuilt: list[int] = []
    skipped: list[int] = []
    failed: list[int] = []

    for m in models:
        assert m.id is not None
        # Newest mesh file wins.
        mesh_file = session.exec(
            select(File)
            .where(File.model_id == m.id, File.file_type.in_(_MESH_TYPES))  # type: ignore[attr-defined]
            .order_by(File.version.desc())  # type: ignore[attr-defined]
        ).first()
        if mesh_file is None:
            skipped.append(m.id)
            continue

        path = Path(mesh_file.path)
        if not path.exists():
            skipped.append(m.id)
            continue

        try:
            thumb_bytes = mesh_processing.render_thumbnail(path)
        except Exception:  # noqa: BLE001 — defensive, log and continue
            logger.exception("rebuild: render_thumbnail crashed for model %s", m.id)
            thumb_bytes = None

        if not thumb_bytes:
            failed.append(m.id)
            continue

        assert mesh_file.id is not None
        thumb_path = storage.thumbnail_path_for(mesh_file.id)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        thumb_path.write_bytes(thumb_bytes)
        m.thumbnail_path = str(thumb_path)
        m.thumbnail_file_id = mesh_file.id
        session.add(m)
        session.commit()
        rebuilt.append(m.id)
        logger.info(
            "rebuild: thumbnail regenerated for model %s file %s", m.id, mesh_file.id
        )

    return {
        "scanned": len(models),
        "rebuilt": rebuilt,
        "skipped_no_mesh": skipped,
        "failed_render": failed,
    }
