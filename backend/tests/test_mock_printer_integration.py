"""End-to-end pipeline test against the mock Moonraker + Spoolman service.

Boots the mock on a real socket, runs the real ``PrinterHub`` WS subscription
against it, and asserts the full chain: simulated print -> job COMPLETED ->
filament grams measured -> Spoolman spool decremented. No provider mocking.
"""

from __future__ import annotations

import asyncio
import time

import httpx
from sqlmodel import Session, select

from app.db.models import File, FileType, Model, PrintJob, PrintJobState, Printer
from app.db.session import get_session_factory
from app.services import runtime_config
from app.services.printer_hub import PrinterHub

from tests.e2e.fakes.mock_printer import create_app
from tests.e2e.fakes.server import start_server

REMOTE = "demo.gcode"


def _seed(db_session: Session, base_url: str) -> tuple[int, int]:
    model = Model(name="Mock", slug="mock-model", hash="z" * 64)
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)

    f = File(
        model_id=model.id,
        path="/data/demo.gcode",
        original_filename=REMOTE,
        file_type=FileType.GCODE,
        version=1,
        size_bytes=100,
        sha256="y" * 64,
    )
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)

    printer = Printer(name="Mock", moonraker_url=base_url)
    db_session.add(printer)
    db_session.commit()
    db_session.refresh(printer)

    job = PrintJob(
        printer_id=printer.id,
        file_id=f.id,
        model_id=model.id,
        remote_filename=REMOTE,
        state=PrintJobState.STARTED,
        spool_id=1,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Enable Spoolman + write-back, pointed at the mock's mounted Spoolman.
    runtime_config.set_spoolman_enabled(db_session, True)
    runtime_config.set_spoolman_write_enabled(db_session, True)
    runtime_config.set_spoolman_config(db_session, base_url=f"{base_url}/spoolman")

    return printer.id, job.id


def test_send_print_completes_and_decrements_spoolman(db_session: Session) -> None:
    app, state = create_app(total_mm=1000.0, total_seconds=10.0, print_seconds=1.5)
    running = start_server(app)
    try:
        printer_id, job_id = _seed(db_session, running.base_url)
        start_weight = state.spools[1]["remaining_weight"]

        # Kick off the simulated print on the printer.
        resp = httpx.post(
            f"{running.base_url}/printer/print/start", params={"filename": REMOTE}
        )
        assert resp.status_code == 200

        async def _drive() -> None:
            hub = PrinterHub()
            stop = asyncio.Event()
            task = asyncio.create_task(hub._run_printer(printer_id, stop))
            deadline = time.time() + 20
            while time.time() < deadline:
                with get_session_factory().session() as s:
                    job = s.get(PrintJob, job_id)
                    if job is not None and job.state == PrintJobState.COMPLETED:
                        break
                await asyncio.sleep(0.2)
            stop.set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(_drive())

        with get_session_factory().session() as s:
            job = s.exec(select(PrintJob).where(PrintJob.id == job_id)).one()
            assert job.state == PrintJobState.COMPLETED
            assert job.filament_used_mm == 1000.0
            assert job.filament_used_g and job.filament_used_g > 0

        assert state.spools[1]["remaining_weight"] < start_weight
    finally:
        running.stop()
