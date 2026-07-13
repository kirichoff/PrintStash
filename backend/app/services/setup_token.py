"""Operator-only credential protecting the unauthenticated first-run setup."""

from __future__ import annotations

import hmac
import secrets

from app.core.config import settings

_generated_setup_token = secrets.token_urlsafe(32)


def current_setup_token() -> str:
    """Return the configured token, or the process-local generated fallback."""
    configured = str(settings.setup_token).strip()
    return configured or _generated_setup_token


def verify_setup_token(candidate: str) -> bool:
    """Constant-time comparison avoids leaking the bootstrap credential."""
    return hmac.compare_digest(candidate, current_setup_token())
