"""First-run setup wizard.

While the install is unconfigured (no ``system_config.configured_at`` and no
users), this router is the *only* write surface that accepts traffic without
auth. Once ``POST /setup`` succeeds, the endpoint becomes read-only and
returns 409 on further attempts — re-running the wizard would let an attacker
seize an established vault.

Storage path validation is intentionally lenient: we try to create the
directory and write a sentinel file. If that works, we accept it. The host
operator is responsible for ensuring the path lives on persistent storage
(usually a Docker volume mount).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.config import FrozenSettings, settings
from app.core.logging import get_logger
from app.db.models import User
from app.db.session import get_session
from app.schemas.setup import SetupRequest, SetupResponse, SetupStatus
from app.services import runtime_config
from app.services.auth import create_access_token, hash_password

logger = get_logger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])


# Pydantic Settings exposes its defaults via ``model_fields``. We pull the
# *original* env-time defaults so the wizard can show the user what they'd
# get if they left the field blank, even after a later edit mutates them.
_DEFAULT_DATA_DIR = str(FrozenSettings.model_fields["data_dir"].default)
_DEFAULT_THUMB_DIR = str(FrozenSettings.model_fields["thumb_dir"].default)


def _validate_writable_dir(path_str: str, label: str) -> Path:
    """Create the directory if needed and confirm we can write into it."""
    try:
        path = Path(path_str).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_{label}_path",
        ) from exc

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("setup: cannot create %s=%s: %s", label, path, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label}_not_creatable",
        ) from exc

    probe = path / ".nexus3d-write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
    except OSError as exc:
        logger.warning("setup: %s=%s not writable: %s", label, path, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label}_not_writable",
        ) from exc
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass

    return path


@router.get("/status", response_model=SetupStatus)
def get_status(session: Session = Depends(get_session)) -> SetupStatus:
    """Lightweight probe — safe to call on every page load."""
    config = runtime_config.get_config(session)
    user_count = len(session.exec(select(User.id)).all())
    configured = config.configured_at is not None and user_count > 0
    return SetupStatus(
        configured=configured,
        user_count=user_count,
        default_data_dir=_DEFAULT_DATA_DIR,
        default_thumb_dir=_DEFAULT_THUMB_DIR,
        current_data_dir=str(settings.data_dir),
        current_thumb_dir=str(settings.thumb_dir),
        configured_at=config.configured_at,
    )


@router.post("", response_model=SetupResponse, status_code=status.HTTP_201_CREATED)
def complete_setup(
    body: SetupRequest, session: Session = Depends(get_session)
) -> SetupResponse:
    """Create the first superuser and (optionally) persist storage paths.

    Refuses to run if the vault is already configured. The wizard hands back a
    JWT so the browser can flow straight into the authenticated app without a
    second round-trip through ``/auth/login``.
    """
    if runtime_config.is_configured(session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already_configured",
        )

    # Guard against a half-configured state (e.g. user table seeded out of band).
    existing = session.exec(select(User).limit(1)).first()
    if existing is not None:
        # An admin already exists from a legacy ensure_default_user run.
        # Block silent first-user creation; operator must use that account.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="users_already_exist",
        )

    # 1. Validate storage paths first — fail fast before mutating anything.
    if body.data_dir:
        _validate_writable_dir(body.data_dir, "data_dir")
    if body.thumb_dir:
        _validate_writable_dir(body.thumb_dir, "thumb_dir")

    # 2. Persist storage overrides (mutates ``settings`` in-place + mkdir).
    if body.data_dir or body.thumb_dir:
        runtime_config.update_storage(
            session,
            data_dir=body.data_dir,
            thumb_dir=body.thumb_dir,
        )

    # 3. Create the superuser.
    user = User(
        username=body.username.strip(),
        email=(body.email.strip() if body.email else None) or None,
        hashed_password=hash_password(body.password),
        is_superuser=True,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # 4. Stamp the config as completed.
    runtime_config.mark_configured(session)

    logger.info(
        "first-run setup complete: user=%s data_dir=%s thumb_dir=%s",
        user.username,
        settings.data_dir,
        settings.thumb_dir,
    )

    token = create_access_token(user.id, user.username, scope="admin")
    return SetupResponse(
        configured=True,
        user_id=user.id,
        username=user.username,
        data_dir=str(settings.data_dir),
        thumb_dir=str(settings.thumb_dir),
        access_token=token,
    )
