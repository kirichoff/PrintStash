from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, backup, config, files, health, ingest, models, printers, setup, taxonomy

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(setup.router)
api_router.include_router(auth.router)
api_router.include_router(ingest.router)
api_router.include_router(models.router)
api_router.include_router(files.router)
api_router.include_router(taxonomy.router)
api_router.include_router(printers.router)
api_router.include_router(backup.router)
api_router.include_router(config.router)
