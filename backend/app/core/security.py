from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency: enforce the shared X-API-Key header on write endpoints.

    When ``settings.api_key`` is empty / unset (local dev), no header is required.
    """
    if not settings.api_key:
        return
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_api_key",
        )
