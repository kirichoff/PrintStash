from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.core.config import settings
from app.db.models import User
from app.db.session import get_session
from app.services.auth import get_user_by_id, verify_access_token


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Optional[str]:
    """FastAPI dependency: enforce the shared X-API-Key header on write endpoints.

    When ``settings.api_key`` is empty / unset (local dev), no header is required.

    Returns the key if valid so it can be combined with JWT auth.
    """
    if not settings.api_key:
        return None
    if x_api_key and x_api_key == settings.api_key:
        return x_api_key
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """FastAPI dependency: extract user from JWT Bearer token.

    Returns None when no valid token is present (read endpoints are open).
    Callers that require a user should check the result or use `require_user`.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer ") :]
    payload = verify_access_token(token)
    if not payload:
        return None
    user_id_str = payload.get("sub")
    if not user_id_str:
        return None
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return None
    user = get_user_by_id(session, user_id)
    if user and user.is_active:
        return user
    return None


async def require_auth(
    api_key_ok: Optional[str] = Depends(require_api_key),
    current_user: Optional[User] = Depends(get_current_user),
) -> None:
    """FastAPI dependency: require EITHER a valid API key OR a valid JWT user.

    Use this on write endpoints to accept both the Stage-1 shared API key
    (for OrcaSlicer hooks, scripts) and Stage-3+ JWT login (for the web frontend).
    """
    if current_user is not None:
        return
    if api_key_ok is not None:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_api_key_or_token",
    )


async def require_user(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """FastAPI dependency: require a valid JWT user (rejects API-key-only).

    Use this on user-profile or password-change endpoints where only a logged-in
    human should be accepted.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )
    return current_user
