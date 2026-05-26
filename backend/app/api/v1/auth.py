"""Authentication endpoints: password login and current-user lookup.

Stage 1 ships a thin local username/password flow that mints a JWT.
Stage 4 will graft OAuth2 / multi-tenant onto the same surface.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.security import require_user
from app.db.session import get_session
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services.auth import authenticate_user, create_access_token

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
    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
def get_me(current_user=Depends(require_user)) -> UserRead:
    """Return the currently logged-in user's profile."""
    return UserRead.model_validate(current_user)
