from __future__ import annotations

import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session

from app.db.models import File
from app.db.session import get_session
from app.services import storage

router = APIRouter(prefix="/files", tags=["files"])


@router.get(
    "/{file_id}/download",
    summary="Download the raw file blob",
    description="Streams the underlying artifact (G-code/STL/3MF/OBJ) from disk.",
)
def download_file(file_id: int, session: Session = Depends(get_session)) -> FileResponse:
    f = session.get(File, file_id)
    if f is None:
        raise HTTPException(status_code=404, detail="file_not_found")
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
    f = session.get(File, file_id)
    if f is None:
        raise HTTPException(status_code=404, detail="file_not_found")
    thumb = storage.thumbnail_path_for(file_id)
    if not thumb.exists():
        raise HTTPException(status_code=404, detail="thumbnail_not_found")
    return FileResponse(path=str(thumb), media_type="image/png")


@router.get(
    "/{file_id}/stl",
    summary="Serve any mesh file as STL for 3D preview",
    description=(
        "If the file is already STL it is served directly.  "
        "3MF and OBJ files are converted to binary STL on the fly via trimesh."
    ),
)
def file_as_stl(file_id: int, session: Session = Depends(get_session)) -> StreamingResponse:
    from app.services import mesh_processing

    f = session.get(File, file_id)
    if f is None:
        raise HTTPException(status_code=404, detail="file_not_found")

    path = Path(f.path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="file_blob_missing")

    suffix = Path(f.original_filename).suffix.lower()

    if suffix == ".stl":
        return FileResponse(
            path=str(path),
            filename=f.original_filename,
            media_type="application/sla",
        )

    stl_bytes = mesh_processing.to_stl_bytes(path)
    if stl_bytes is None:
        raise HTTPException(status_code=500, detail="stl_conversion_failed")

    return StreamingResponse(
        io.BytesIO(stl_bytes),
        media_type="application/sla",
        headers={"Content-Disposition": f'attachment; filename="{Path(f.original_filename).stem}.stl"'},
    )
