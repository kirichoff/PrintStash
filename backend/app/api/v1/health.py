from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns service identity and version. Used by Docker healthcheck.",
)
def health() -> dict:
    return {
        "status": "ok",
        "name": settings.app_name,
        "version": settings.app_version,
    }
