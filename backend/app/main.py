from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_session_factory, init_db
from app.services.printer_hub import PrinterHub
from app.services.runtime_config import apply_overlay, is_configured
from app.services.storage_backend import init_backend

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting %s v%s", settings.app_name, settings.app_version)
    # DB must exist before we can read the runtime overlay.
    init_db()
    with get_session_factory().scoped_session() as session:
        apply_overlay(session)
        configured = is_configured(session)
    # Initialise storage backend (creates dirs or validates S3 bucket).
    _backend = init_backend()
    if not configured:
        logger.warning(
            "vault is unconfigured — open the web UI to run the first-run setup wizard"
        )
    logger.info(
        "backend=%s data_dir=%s thumb_dir=%s db=%s",
        settings.storage_backend,
        settings.data_dir,
        settings.thumb_dir,
        settings.db_url,
    )
    hub = PrinterHub()
    app.state.printer_hub = hub
    await hub.start_all()
    yield
    logger.info("shutting down printer hub")
    await hub.stop_all()
    logger.info("shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Self-hosted, Plex-style asset management for 3D printing workflows. "
        "Stages 1–3: headless API, OrcaSlicer ingestion, categories/tags, and "
        "Klipper/Moonraker integration with live state + print history."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
