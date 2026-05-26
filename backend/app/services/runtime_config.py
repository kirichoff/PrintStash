"""Runtime overlay for storage settings.

The Pydantic ``Settings`` object is built once at import time from environment
variables. The first-run setup wizard (and any future admin UI) may persist
storage paths into the ``system_config`` table; on startup we *overlay* those
DB values back onto the ``settings`` singleton so the rest of the codebase can
keep reading ``settings.data_dir`` / ``settings.thumb_dir`` exactly as before.

This module is intentionally tiny: write to DB → mutate ``settings`` →
``ensure_dirs()``. Reads remain free (no extra query per request).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.core.config import ensure_dirs, settings
from app.core.logging import get_logger
from app.core.time import utcnow
from app.db.models import SystemConfig, User

logger = get_logger(__name__)


def get_or_create(session: Session) -> SystemConfig:
    """Return the singleton config row, creating an empty one if missing."""
    config = session.get(SystemConfig, 1)
    if config is None:
        config = SystemConfig(id=1)
        session.add(config)
        session.commit()
        session.refresh(config)
    return config


def get_config(session: Session) -> SystemConfig:
    return get_or_create(session)


def is_configured(session: Session) -> bool:
    """True once the setup wizard has run *and* at least one user exists.

    Both checks matter: if the DB is wiped but a stale ``system_config`` row
    survives somehow, we still surface the wizard.
    """
    config = session.get(SystemConfig, 1)
    if config is None or config.configured_at is None:
        return False
    has_user = session.exec(select(User.id).limit(1)).first() is not None
    return has_user


def apply_overlay(session: Session) -> None:
    """Copy persisted overrides from ``system_config`` into ``settings``.

    Safe to call on every startup. If the row doesn't exist yet, we no-op
    rather than create one (the wizard will create it on completion).
    """
    config = session.get(SystemConfig, 1)
    if config is None:
        return
    if config.data_dir:
        settings.data_dir = Path(config.data_dir)
    if config.thumb_dir:
        settings.thumb_dir = Path(config.thumb_dir)


def update_storage(
    session: Session,
    *,
    data_dir: Optional[str] = None,
    thumb_dir: Optional[str] = None,
) -> SystemConfig:
    """Persist storage overrides, mutate the live ``settings``, and mkdir."""
    config = get_or_create(session)
    if data_dir is not None:
        config.data_dir = data_dir
        settings.data_dir = Path(data_dir)
    if thumb_dir is not None:
        config.thumb_dir = thumb_dir
        settings.thumb_dir = Path(thumb_dir)
    config.updated_at = utcnow()
    session.add(config)
    session.commit()
    session.refresh(config)
    ensure_dirs()
    logger.info(
        "runtime storage updated: data_dir=%s thumb_dir=%s",
        settings.data_dir,
        settings.thumb_dir,
    )
    return config


def mark_configured(session: Session) -> SystemConfig:
    config = get_or_create(session)
    if config.configured_at is None:
        config.configured_at = utcnow()
    config.updated_at = utcnow()
    session.add(config)
    session.commit()
    session.refresh(config)
    return config
