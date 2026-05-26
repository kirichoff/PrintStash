"""Pydantic DTOs for the first-run setup wizard."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SetupStatus(BaseModel):
    """Reported by ``GET /api/v1/setup/status``.

    ``configured`` is the bool the frontend gates on. The rest are read-only
    hints for the wizard UI so it can pre-fill sensible defaults.
    """

    configured: bool
    user_count: int
    default_data_dir: str
    default_thumb_dir: str
    current_data_dir: str
    current_thumb_dir: str
    configured_at: Optional[datetime] = None


class SetupRequest(BaseModel):
    """Payload for ``POST /api/v1/setup`` — only accepted while unconfigured."""

    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    email: Optional[str] = Field(default=None, max_length=255)
    data_dir: Optional[str] = Field(default=None, max_length=1024)
    thumb_dir: Optional[str] = Field(default=None, max_length=1024)


class SetupResponse(BaseModel):
    """Returned on successful first-run completion."""

    configured: bool
    user_id: int
    username: str
    data_dir: str
    thumb_dir: str
    access_token: str
    token_type: str = "bearer"
