"""Printer management + send-to-print + live WS status (Stage 3 / The Hub)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from sqlmodel import Session, select

from app.core.logging import get_logger
from app.core.security import require_api_key
from app.db.models import File, FileType, PrintJob, PrintJobState, Printer
from app.db.session import get_session
from app.schemas.printers import (
    PrinterCreate,
    PrinterRead,
    PrinterUpdate,
    PrintJobRead,
    SendToPrinter,
)
from app.services.moonraker import MoonrakerClient, MoonrakerError
from app.services.printer_hub import PrinterHub, get_hub, get_hub_from_ws

logger = get_logger(__name__)

router = APIRouter(prefix="/printers", tags=["printers"])


def _to_read(p: Printer) -> PrinterRead:
    return PrinterRead(
        id=p.id,  # type: ignore[arg-type]
        name=p.name,
        moonraker_url=p.moonraker_url,
        has_api_key=bool(p.api_key),
        notes=p.notes,
        status=p.status,
        last_seen_at=p.last_seen_at,
        last_error=p.last_error,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


# -- Printer CRUD --------------------------------------------------------


@router.get("", response_model=List[PrinterRead], summary="List printers")
def list_printers(session: Session = Depends(get_session)) -> List[PrinterRead]:
    return [
        _to_read(p) for p in session.exec(select(Printer).order_by(Printer.name)).all()
    ]


@router.get("/{printer_id}", response_model=PrinterRead, summary="Get a printer")
def get_printer(
    printer_id: int, session: Session = Depends(get_session)
) -> PrinterRead:
    p = session.get(Printer, printer_id)
    if p is None:
        raise HTTPException(status_code=404, detail="printer_not_found")
    return _to_read(p)


@router.post(
    "",
    response_model=PrinterRead,
    status_code=201,
    dependencies=[Depends(require_api_key)],
    summary="Register a new printer",
)
async def create_printer(
    payload: PrinterCreate,
    session: Session = Depends(get_session),
    hub: PrinterHub = Depends(get_hub),
) -> PrinterRead:
    p = Printer(
        name=payload.name.strip(),
        moonraker_url=payload.moonraker_url.strip().rstrip("/"),
        api_key=payload.api_key or None,
        notes=payload.notes,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    assert p.id is not None
    await hub.add_printer(p.id)
    return _to_read(p)


@router.patch(
    "/{printer_id}",
    response_model=PrinterRead,
    dependencies=[Depends(require_api_key)],
    summary="Update a printer",
)
async def update_printer(
    printer_id: int,
    payload: PrinterUpdate,
    session: Session = Depends(get_session),
    hub: PrinterHub = Depends(get_hub),
) -> PrinterRead:
    p = session.get(Printer, printer_id)
    if p is None:
        raise HTTPException(status_code=404, detail="printer_not_found")
    if payload.name is not None:
        p.name = payload.name.strip() or p.name
    if payload.moonraker_url is not None:
        p.moonraker_url = payload.moonraker_url.strip().rstrip("/")
    if payload.api_key is not None:
        p.api_key = payload.api_key or None
    if payload.notes is not None:
        p.notes = payload.notes
    p.updated_at = datetime.utcnow()
    session.add(p)
    session.commit()
    session.refresh(p)
    await hub.restart_printer(printer_id)
    return _to_read(p)


@router.delete(
    "/{printer_id}",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(require_api_key)],
    summary="Remove a printer",
)
async def delete_printer(
    printer_id: int,
    session: Session = Depends(get_session),
    hub: PrinterHub = Depends(get_hub),
):
    p = session.get(Printer, printer_id)
    if p is None:
        raise HTTPException(status_code=404, detail="printer_not_found")
    session.delete(p)
    session.commit()
    await hub.remove_printer(printer_id)
    return Response(status_code=204)


# -- Send-to-print + control ---------------------------------------------


@router.post(
    "/{printer_id}/send",
    response_model=PrintJobRead,
    dependencies=[Depends(require_api_key)],
    summary="Upload a vault file to the printer (optionally start the print)",
    description=(
        "Streams the chosen vault File to Moonraker's gcode store. The File must "
        "be a .gcode artifact. If start_print is true, Moonraker is asked to start "
        "the print immediately after upload."
    ),
)
async def send_to_printer(
    printer_id: int, payload: SendToPrinter, session: Session = Depends(get_session)
) -> PrintJobRead:
    p = session.get(Printer, printer_id)
    if p is None:
        raise HTTPException(status_code=404, detail="printer_not_found")
    f = session.get(File, payload.file_id)
    if f is None:
        raise HTTPException(status_code=404, detail="file_not_found")
    if f.file_type != FileType.GCODE:
        raise HTTPException(status_code=400, detail="file_not_gcode")
    local = Path(f.path)
    if not local.exists():
        raise HTTPException(status_code=410, detail="file_blob_missing")

    remote_name = (payload.remote_filename or f.original_filename).strip()
    if not remote_name.lower().endswith((".gcode", ".g", ".gco")):
        remote_name += ".gcode"

    job = PrintJob(
        printer_id=printer_id,
        file_id=f.id,  # type: ignore[arg-type]
        model_id=f.model_id,
        remote_filename=remote_name,
        state=PrintJobState.UPLOADING,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    client = MoonrakerClient(p.moonraker_url, p.api_key)
    try:
        await client.upload_gcode(local, remote_name, start_print=payload.start_print)
        if payload.start_print:
            # Moonraker accepts print=true on upload, but it returns immediately;
            # the print_stats subscription will move the job into PRINTING. We mark
            # STARTED here optimistically.
            job.state = PrintJobState.STARTED
        else:
            job.state = PrintJobState.QUEUED
        job.updated_at = datetime.utcnow()
    except MoonrakerError as exc:
        job.state = PrintJobState.FAILED
        job.error = str(exc)
        job.finished_at = datetime.utcnow()
        session.add(job)
        session.commit()
        raise HTTPException(status_code=502, detail=f"moonraker_error: {exc}")

    session.add(job)
    session.commit()
    session.refresh(job)
    return PrintJobRead(**job.model_dump())


@router.post(
    "/{printer_id}/pause",
    dependencies=[Depends(require_api_key)],
    summary="Pause the current print",
)
async def pause_printer(
    printer_id: int, session: Session = Depends(get_session)
) -> dict:
    p = session.get(Printer, printer_id)
    if p is None:
        raise HTTPException(status_code=404, detail="printer_not_found")
    try:
        await MoonrakerClient(p.moonraker_url, p.api_key).pause_print()
    except MoonrakerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"ok": True}


@router.post(
    "/{printer_id}/resume",
    dependencies=[Depends(require_api_key)],
    summary="Resume the paused print",
)
async def resume_printer(
    printer_id: int, session: Session = Depends(get_session)
) -> dict:
    p = session.get(Printer, printer_id)
    if p is None:
        raise HTTPException(status_code=404, detail="printer_not_found")
    try:
        await MoonrakerClient(p.moonraker_url, p.api_key).resume_print()
    except MoonrakerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"ok": True}


@router.post(
    "/{printer_id}/cancel",
    dependencies=[Depends(require_api_key)],
    summary="Cancel the current print",
)
async def cancel_printer(
    printer_id: int, session: Session = Depends(get_session)
) -> dict:
    p = session.get(Printer, printer_id)
    if p is None:
        raise HTTPException(status_code=404, detail="printer_not_found")
    try:
        await MoonrakerClient(p.moonraker_url, p.api_key).cancel_print()
    except MoonrakerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"ok": True}


# -- Live snapshots & print history --------------------------------------


@router.get(
    "/{printer_id}/status",
    summary="One-shot snapshot of cached printer state",
)
def printer_status(
    printer_id: int,
    session: Session = Depends(get_session),
    hub: PrinterHub = Depends(get_hub),
) -> dict:
    p = session.get(Printer, printer_id)
    if p is None:
        raise HTTPException(status_code=404, detail="printer_not_found")
    return {
        "printer": _to_read(p).model_dump(mode="json"),
        "snapshot": hub.snapshots.get(printer_id, {}),
    }


@router.get(
    "/{printer_id}/jobs",
    response_model=List[PrintJobRead],
    summary="List recent print jobs for a printer",
)
def list_jobs(
    printer_id: int,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> List[PrintJobRead]:
    rows = session.exec(
        select(PrintJob)
        .where(PrintJob.printer_id == printer_id)
        .order_by(PrintJob.created_at.desc())  # type: ignore[attr-defined]
        .limit(limit)
    ).all()
    return [PrintJobRead(**j.model_dump()) for j in rows]


@router.websocket("/{printer_id}/ws")
async def printer_ws(
    websocket: WebSocket,
    printer_id: int,
    hub: PrinterHub = Depends(get_hub_from_ws),
) -> None:
    """Live status stream for a single printer.

    Pushes JSON messages of the form:
        {"type": "snapshot", "printer_id": <id>, "data": {...full snapshot...}}
        {"type": "update",   "printer_id": <id>, "data": {...changed objects...}}
    """
    await websocket.accept()
    await hub.attach(printer_id, websocket)
    try:
        while True:
            # We don't need anything from the client right now; just block.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.detach(printer_id, websocket)
