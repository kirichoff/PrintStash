"""Runtime overlay for all configurable settings.

The Pydantic ``Settings`` object is built once at import time from environment
variables. The first-run setup wizard and the Settings UI may persist overrides
into the ``system_config`` table; on startup we *overlay* those DB values back
onto the ``settings`` singleton so the rest of the codebase can keep reading
``settings.xxx`` exactly as before.
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
    if config.storage_backend:
        settings.storage_backend = config.storage_backend
    if config.s3_bucket:
        settings.s3_bucket = config.s3_bucket
    if config.s3_endpoint_url:
        settings.s3_endpoint_url = config.s3_endpoint_url
    if config.s3_region:
        settings.s3_region = config.s3_region
    if config.s3_access_key:
        settings.s3_access_key = config.s3_access_key
    if config.s3_secret_key:
        settings.s3_secret_key = config.s3_secret_key
    if config.backup_retention_days is not None:
        settings.backup_retention_days = config.backup_retention_days
    if config.backup_s3_bucket:
        settings.backup_s3_bucket = config.backup_s3_bucket
    if config.backup_s3_endpoint_url:
        settings.backup_s3_endpoint_url = config.backup_s3_endpoint_url
    if config.backup_s3_region:
        settings.backup_s3_region = config.backup_s3_region
    if config.backup_s3_access_key:
        settings.backup_s3_access_key = config.backup_s3_access_key
    if config.backup_s3_secret_key:
        settings.backup_s3_secret_key = config.backup_s3_secret_key


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


def _env_or_default(field_name: str) -> object:
    """Return the effective env-var value for *field_name* or its model default."""
    import os

    from app.core.config import Settings

    env_key = f"VAULT_{field_name.upper()}"
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val
    field = Settings.model_fields.get(field_name)
    if field is not None and field.default is not None:
        return field.default
    return ""


def update_config(
    session: Session,
    *,
    storage_backend: Optional[str] = None,
    data_dir: Optional[str] = None,
    thumb_dir: Optional[str] = None,
    s3_bucket: Optional[str] = None,
    s3_endpoint_url: Optional[str] = None,
    s3_region: Optional[str] = None,
    s3_access_key: Optional[str] = None,
    s3_secret_key: Optional[str] = None,
    backup_retention_days: Optional[int] = None,
    backup_s3_bucket: Optional[str] = None,
    backup_s3_endpoint_url: Optional[str] = None,
    backup_s3_region: Optional[str] = None,
    backup_s3_access_key: Optional[str] = None,
    backup_s3_secret_key: Optional[str] = None,
) -> SystemConfig:
    """Persist config overrides and mutate ``settings`` in-place.

    Pass ``None`` for a field to leave it unchanged. Pass an empty string to
    clear the override (fall back to env/default). Pass a value to set.
    """
    config = get_or_create(session)

    def _apply_str(field_name: str, value: Optional[str]) -> None:
        if value is None:
            return
        db_val = value if value != "" else None
        setattr(config, field_name, db_val)
        effective: object = db_val if db_val is not None else _env_or_default(field_name)
        if field_name in ("data_dir", "thumb_dir") and effective:
            effective = Path(str(effective))
        setattr(settings, field_name, effective)

    def _apply_int(field_name: str, value: Optional[int]) -> None:
        if value is None:
            return
        db_val = value if value != -1 else None
        setattr(config, field_name, db_val)
        if db_val is not None:
            setattr(settings, field_name, db_val)
        else:
            fallback = _env_or_default(field_name)
            try:
                setattr(settings, field_name, int(fallback or 0))
            except (ValueError, TypeError):
                setattr(settings, field_name, 30)

    _apply_str("storage_backend", storage_backend)
    _apply_str("data_dir", data_dir)
    _apply_str("thumb_dir", thumb_dir)
    _apply_str("s3_bucket", s3_bucket)
    _apply_str("s3_endpoint_url", s3_endpoint_url)
    _apply_str("s3_region", s3_region)
    _apply_str("s3_access_key", s3_access_key)
    _apply_str("s3_secret_key", s3_secret_key)
    _apply_int("backup_retention_days", backup_retention_days)
    _apply_str("backup_s3_bucket", backup_s3_bucket)
    _apply_str("backup_s3_endpoint_url", backup_s3_endpoint_url)
    _apply_str("backup_s3_region", backup_s3_region)
    _apply_str("backup_s3_access_key", backup_s3_access_key)
    _apply_str("backup_s3_secret_key", backup_s3_secret_key)

    config.updated_at = utcnow()
    session.add(config)
    session.commit()
    session.refresh(config)

    logger.info("runtime config updated")
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


def get_effective_config(session: Session) -> dict:
    """Return the current effective config (env + DB overlay merged)."""
    config = session.get(SystemConfig, 1)

    return {
        "storage_backend": config.storage_backend if config and config.storage_backend else settings.storage_backend,
        "data_dir": str(settings.data_dir),
        "thumb_dir": str(settings.thumb_dir),
        "s3_bucket": config.s3_bucket if config and config.s3_bucket else settings.s3_bucket,
        "s3_endpoint_url": config.s3_endpoint_url if config and config.s3_endpoint_url else settings.s3_endpoint_url,
        "s3_region": config.s3_region if config and config.s3_region else settings.s3_region,
        "s3_access_key": _mask_secret(
            config.s3_access_key if config and config.s3_access_key else settings.s3_access_key
        ),
        "s3_secret_key": _mask_secret(
            config.s3_secret_key if config and config.s3_secret_key else settings.s3_secret_key
        ),
        "has_s3_access_key": bool(
            (config and config.s3_access_key) or settings.s3_access_key
        ),
        "has_s3_secret_key": bool(
            (config and config.s3_secret_key) or settings.s3_secret_key
        ),
        "backup_retention_days": (
            config.backup_retention_days
            if config and config.backup_retention_days is not None
            else settings.backup_retention_days
        ),
        "backup_s3_bucket": config.backup_s3_bucket if config and config.backup_s3_bucket else settings.backup_s3_bucket,
        "backup_s3_endpoint_url": config.backup_s3_endpoint_url if config and config.backup_s3_endpoint_url else settings.backup_s3_endpoint_url,
        "backup_s3_region": config.backup_s3_region if config and config.backup_s3_region else settings.backup_s3_region,
        "backup_s3_access_key": _mask_secret(
            config.backup_s3_access_key if config and config.backup_s3_access_key else settings.backup_s3_access_key
        ),
        "backup_s3_secret_key": _mask_secret(
            config.backup_s3_secret_key if config and config.backup_s3_secret_key else settings.backup_s3_secret_key
        ),
        "has_backup_s3_access_key": bool(
            (config and config.backup_s3_access_key) or settings.backup_s3_access_key
        ),
        "has_backup_s3_secret_key": bool(
            (config and config.backup_s3_secret_key) or settings.backup_s3_secret_key
        ),
        "has_backup_s3": bool(
            (config and config.backup_s3_bucket) or settings.backup_s3_bucket
        ),
    }


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]
