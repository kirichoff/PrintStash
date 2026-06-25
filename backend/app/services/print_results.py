"""Post-print outcome helpers shared by the live printer hub and history import.

Keeps the "what a finished print means for a revision" logic in one place:
material lookup for filament-mass derivation, and the auto-promotion of a
revision to ``known_good`` after a successful print.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.db.models import (
    File,
    FileRevisionStatus,
    FilamentProfile,
    Metadata,
    PrintJob,
)

logger = get_logger(__name__)


def material_type_for_file(session: Session, file_id: int) -> str | None:
    """Material type recorded on the printed file's metadata, if any."""
    meta = session.exec(select(Metadata).where(Metadata.file_id == file_id)).first()
    return meta.material_type if meta else None


def linked_profile_for_spool(
    session: Session, spool_filament_id: int | None
) -> FilamentProfile | None:
    """The synced FilamentProfile mirroring a spool's Spoolman filament, if any.

    Lets a print resolve real density/diameter/cost locally (sync already
    mirrored them) without a live Spoolman call at the finishing tick.
    """
    if spool_filament_id is None:
        return None
    return session.exec(
        select(FilamentProfile).where(
            FilamentProfile.spoolman_filament_id == spool_filament_id
        )
    ).first()


def mark_known_good_if_eligible(session: Session, file_id: int) -> bool:
    """Promote a revision to known_good after a successful print.

    Only promotes when the status is unset or ``needs_test`` — a human's
    ``failed``/``archived`` verdict is never overridden. Returns True if it
    changed the status. The caller is responsible for the feature toggle.
    """
    f = session.get(File, file_id)
    if f is None or f.deleted_at is not None:
        return False
    if f.revision_status in (None, FileRevisionStatus.NEEDS_TEST):
        f.revision_status = FileRevisionStatus.KNOWN_GOOD
        session.add(f)
        session.commit()
        logger.info("auto-marked file %s known_good after successful print", file_id)
        return True
    return False


def record_spool_usage(session: Session, job: PrintJob) -> bool:
    """Write a measured print's consumption back to its Spoolman spool.

    No-ops (returns False) unless every precondition holds: Spoolman enabled,
    write-back enabled, a spool was selected on the job, and the print reported
    measured grams. Moonraker-measured prints only — Bambu reports no live
    consumption, so ``filament_used_g`` is None and this returns early.

    Decrement happens server-side in Spoolman. A Spoolman outage is logged and
    swallowed — the print is already recorded and must never be blocked. The
    caller invokes this once per job (on the finishing tick), so the spool is
    never decremented twice for the same print.
    """
    # Imported here to avoid importing the service layer at module load (keeps
    # print_results dependency-light and dodges any import cycle).
    from app.services import runtime_config
    from app.services.spoolman import SpoolmanError, use_spool_weight_sync

    if job.spool_id is None or not job.filament_used_g:
        return False
    if not runtime_config.spoolman_enabled(session):
        return False
    if not runtime_config.spoolman_write_enabled(session):
        return False
    config = runtime_config.spoolman_config(session)
    base_url = config.get("base_url")
    if not base_url:
        return False
    try:
        use_spool_weight_sync(
            base_url, config.get("api_key"), job.spool_id, float(job.filament_used_g)
        )
    except SpoolmanError as exc:
        logger.warning(
            "Spoolman consumption write-back failed for job %s (spool %s): %s",
            job.id,
            job.spool_id,
            exc,
        )
        return False
    except Exception:  # never let a Spoolman hiccup escape into the print path
        logger.exception(
            "unexpected error writing consumption to Spoolman for job %s", job.id
        )
        return False
    logger.info(
        "decremented Spoolman spool %s by %.2fg for job %s",
        job.spool_id,
        job.filament_used_g,
        job.id,
    )
    return True
