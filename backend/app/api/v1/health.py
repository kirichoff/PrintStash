from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.services.storage_backend import get_backend

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns service identity and version. Used by Docker healthcheck.",
)
def health() -> dict:
    out = {
        "status": "ok",
        "name": settings.app_name,
        "version": settings.app_version,
    }
    if settings.storage_backend == "s3":
        probe = get_backend().health_probe()
        out["storage"] = probe
        if not probe.get("ok", False):
            out["status"] = "degraded"
    return out
