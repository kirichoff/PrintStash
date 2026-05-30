"""Authentication endpoints: password login and current-user lookup.

Stage 1 ships a thin local username/password flow that mints a JWT.
Stage 4 will graft OAuth2 / multi-tenant onto the same surface.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.security import oauth2_scheme, require_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserRead,
)
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    revoke_access_token,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    """Authenticate with username + password and receive a JWT access token."""
    user = authenticate_user(session, body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )
    scope = "admin" if user.is_superuser else "write"
    access_token = create_access_token(user.id, user.username, scope=scope)
    refresh_token = create_refresh_token(session, user_id=user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        scope=scope,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest, session: Session = Depends(get_session)
) -> TokenResponse:
    """Exchange a valid refresh token for a new access+refresh token pair."""
    old_token = rotate_refresh_token(session, body.refresh_token)
    if old_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_refresh_token",
        )
    user = session.get(User, old_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_refresh_token",
        )
    scope = "admin" if user.is_superuser else "write"
    access_token = create_access_token(user.id, user.username, scope=scope)
    refresh_token = create_refresh_token(session, user_id=user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        scope=scope,
    )


@router.post("/logout")
def logout(
    body: LogoutRequest | None = None,
    session: Session = Depends(get_session),
    token: str | None = Depends(oauth2_scheme),
) -> dict:
    """Invalidate access token and optionally revoke refresh token."""
    if token:
        revoke_access_token(token)
    if body and body.refresh_token:
        revoke_refresh_token(session, body.refresh_token)
    return {"ok": True}


@router.get("/me", response_model=UserRead)
def get_me(current_user=Depends(require_user)) -> UserRead:
    """Return the currently logged-in user's profile."""
    return UserRead.model_validate(current_user)
