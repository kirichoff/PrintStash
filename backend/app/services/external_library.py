"""External library (NAS folder) scan + reconcile engine.

The folder is the source of truth. A scan walks ``root_path`` and reconciles the
index against what is on disk: new files are indexed in place (no copy), removed
files are moved to trash, and changed files are re-hashed and refreshed. Web
uploads/revisions write back into the folder (see ``ingestion.resolve_write_target``)
so the folder stays complete — PrintStash never overwrites or deletes existing bytes.

Safety: a scan never mass-deletes on an unmounted/empty root. If ``root_path`` is
missing/unreadable, or it yields zero candidate files while the library still has
live indexed files, the scan aborts with an error and changes nothing.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.core.time import utcnow
from app.db.models import (
    ExternalLibrary,
    ExternalLibraryCollectionMode,
    ExternalLibraryScanStatus,
    File,
    FileType,
    Metadata,
    Model,
    SUFFIX_TO_FILE_TYPE,
)
from app.db.scopes import live
from app.db.session import SessionFactory, get_session_factory
from app.services import taxonomy, thumbnail
from app.services.hashing import sha256_file
from app.services.ingestion import (
    _gcode_strategy,
    _mesh_strategy,
    persist_artifact,
    resolve_or_create_model,
)
from app.services.jobs import registry
from app.services.profile_detection import upsert_detected_profiles
from app.services.storage_backend import get_backend

logger = get_logger(__name__)

_MTIME_TOLERANCE_S = 1e-6


@dataclass
class ScanSummary:
    added: int = 0
    updated: int = 0
    removed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    error: Optional[str] = None
    aborted: bool = False

    def as_dict(self) -> dict:
        return {
            "added": self.added,
            "updated": self.updated,
            "removed": self.removed,
            "skipped": self.skipped,
            "errors": self.errors,
            "error": self.error,
            "aborted": self.aborted,
        }


def _strategy_for(file_type: FileType):
    if file_type == FileType.GCODE:
        return _gcode_strategy()
    return _mesh_strategy(file_type)


def _walk(root: Path) -> dict[str, tuple[int, float]]:
    """Map every supported file under *root* to (size_bytes, mtime)."""
    disk: dict[str, tuple[int, float]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUFFIX_TO_FILE_TYPE:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        disk[str(path)] = (st.st_size, st.st_mtime)
    return disk


def _collection_path_for(
    session: Session, library: ExternalLibrary, source_path: Path
) -> Optional[str]:
    """Resolve the collection (raw '/'-joined) path for a scanned file."""
    if library.collection_mode == ExternalLibraryCollectionMode.MIRROR:
        try:
            rel = source_path.parent.relative_to(Path(library.root_path))
        except ValueError:
            return None
        parts = [p for p in rel.parts if p not in ("", ".")]
        return "/".join(parts) if parts else None
    # SINGLE mode: everything lands in the configured target collection.
    if library.target_collection_id is not None:
        from app.db.models import Collection

        coll = session.get(Collection, library.target_collection_id)
        if coll is not None and coll.deleted_at is None:
            return coll.path
    return None


def _index_external_file(
    session: Session,
    library: ExternalLibrary,
    source_path: Path,
    size: int,
    mtime: float,
) -> None:
    """Index a not-yet-known on-disk file as an external (in-place) artifact."""
    file_type = SUFFIX_TO_FILE_TYPE[source_path.suffix.lower()]
    blob_hash = sha256_file(source_path)
    strategy = _strategy_for(file_type)
    meta, thumb_bytes = strategy.process(source_path)

    model, created = resolve_or_create_model(
        session,
        dedup_hash=blob_hash,
        model_name=source_path.stem,
        actor=None,
    )

    if created or model.collection_id is None:
        coll_path = _collection_path_for(session, library, source_path)
        if coll_path:
            coll = taxonomy.resolve_or_create_collection(session, coll_path)
            if coll is not None:
                model.collection_id = coll.id
                session.add(model)
                session.commit()
                session.refresh(model)

    persist_artifact(
        session,
        model=model,
        staged_path=source_path,
        original_filename=source_path.name,
        file_type=file_type,
        blob_hash=blob_hash,
        meta=meta,
        thumb_bytes=thumb_bytes,
        overwrite_thumbnail=strategy.overwrite_thumbnail,
        move_blob=False,
        dest_key_override=str(source_path),
        is_external=True,
        external_library_id=library.id,
        source_mtime=mtime,
    )
    upsert_detected_profiles(session, meta)


def _reindex_changed(
    session: Session,
    file_row: File,
    source_path: Path,
    size: int,
    mtime: float,
) -> bool:
    """Refresh an indexed file whose on-disk size/mtime changed.

    Returns True if the content actually changed (re-parsed + thumbnail rebuilt),
    False when only the mtime moved (we just record the new signature)."""
    new_hash = sha256_file(source_path)
    if new_hash == file_row.sha256:
        file_row.size_bytes = size
        file_row.source_mtime = mtime
        session.add(file_row)
        session.commit()
        return False

    file_type = SUFFIX_TO_FILE_TYPE[source_path.suffix.lower()]
    strategy = _strategy_for(file_type)
    meta, thumb_bytes = strategy.process(source_path)

    file_row.sha256 = new_hash
    file_row.size_bytes = size
    file_row.source_mtime = mtime
    file_row.uploaded_at = utcnow()
    session.add(file_row)
    session.commit()
    session.refresh(file_row)

    backend = get_backend()
    assert file_row.id is not None
    if thumb_bytes:
        backend.write_bytes(thumbnail.to_webp(thumb_bytes), backend.thumbnail_key(file_row.id))
        backend.delete(backend.legacy_thumbnail_key(file_row.id))

    md = session.exec(select(Metadata).where(Metadata.file_id == file_row.id)).first()
    md_fields = {k: v for k, v in meta.items() if k in Metadata.model_fields}
    if md is None:
        session.add(Metadata(file_id=file_row.id, **md_fields))
    else:
        for k, v in md_fields.items():
            setattr(md, k, v)
        session.add(md)
    session.commit()
    upsert_detected_profiles(session, meta)
    return True


def _remove_external_file(session: Session, file_row: File) -> None:
    """Soft-delete a file whose on-disk source is gone; trash the model if it
    becomes empty. NAS bytes are never touched (the file is already gone)."""
    now = utcnow()
    file_row.deleted_at = now
    session.add(file_row)
    session.commit()

    remaining = session.exec(
        select(File).where(File.model_id == file_row.model_id, live(File))
    ).first()
    if remaining is None:
        model = session.get(Model, file_row.model_id)
        if model is not None and model.deleted_at is None:
            model.deleted_at = now
            model.updated_at = now
            session.add(model)
            session.commit()


def _finish(
    session: Session,
    library: ExternalLibrary,
    status: ExternalLibraryScanStatus,
    summary: ScanSummary,
) -> None:
    library.last_scanned_at = utcnow()
    library.last_scan_status = status
    library.last_scan_summary = json.dumps(summary.as_dict())
    library.updated_at = utcnow()
    session.add(library)
    session.commit()


def scan_library(
    library_id: int,
    *,
    job_id: Optional[str] = None,
    session_factory: SessionFactory | None = None,
) -> dict:
    """Reconcile a library's index with its on-disk folder. Returns the summary."""
    if session_factory is None:
        session_factory = get_session_factory()

    summary = ScanSummary()
    with session_factory.scoped_session() as session:
        library = session.get(ExternalLibrary, library_id)
        if library is None:
            raise ValueError(f"external library {library_id} not found")

        library.last_scan_status = ExternalLibraryScanStatus.RUNNING
        session.add(library)
        session.commit()

        root = Path(library.root_path)

        # --- Safety guard: never mass-delete on an unmounted/unreadable root. ---
        if not root.exists() or not root.is_dir() or not os.access(root, os.R_OK):
            summary.error = "root_path_missing_or_unreadable"
            summary.aborted = True
            _finish(session, library, ExternalLibraryScanStatus.ERROR, summary)
            logger.warning(
                "scan[lib=%s] aborted: root %s missing/unreadable", library_id, root
            )
            if job_id:
                registry.update(job_id, state="failed", error=summary.error)
            return summary.as_dict()

        disk = _walk(root)

        live_files = session.exec(
            select(File).where(
                File.external_library_id == library_id,
                live(File),
            )
        ).all()
        db_by_path = {f.path: f for f in live_files}

        if not disk and db_by_path:
            summary.error = "root_empty_aborted"
            summary.aborted = True
            _finish(session, library, ExternalLibraryScanStatus.ERROR, summary)
            logger.warning(
                "scan[lib=%s] aborted: root %s empty but %d indexed files exist",
                library_id,
                root,
                len(db_by_path),
            )
            if job_id:
                registry.update(job_id, state="failed", error=summary.error)
            return summary.as_dict()

        if job_id:
            registry.update(job_id, state="running", total_steps=len(disk) or 1)

        for index, (path, (size, mtime)) in enumerate(disk.items(), start=1):
            if job_id:
                registry.update(
                    job_id,
                    step=index,
                    total_steps=len(disk),
                    label=f"scanning {Path(path).name}",
                    progress=index / len(disk) * 100,
                )
            existing = db_by_path.get(path)
            try:
                if existing is None:
                    _index_external_file(session, library, Path(path), size, mtime)
                    summary.added += 1
                elif (
                    existing.size_bytes == size
                    and existing.source_mtime is not None
                    and abs(existing.source_mtime - mtime) <= _MTIME_TOLERANCE_S
                ):
                    summary.skipped += 1
                else:
                    if _reindex_changed(session, existing, Path(path), size, mtime):
                        summary.updated += 1
                    else:
                        summary.skipped += 1
            except Exception as exc:  # noqa: BLE001 — per-file boundary, keep scanning
                logger.exception("scan[lib=%s] failed on %s", library_id, path)
                summary.errors.append(f"{path}: {exc}")

        for path, file_row in db_by_path.items():
            if path not in disk:
                _remove_external_file(session, file_row)
                summary.removed += 1

        _finish(session, library, ExternalLibraryScanStatus.OK, summary)
        logger.info(
            "scan[lib=%s] done added=%d updated=%d removed=%d skipped=%d errors=%d",
            library_id,
            summary.added,
            summary.updated,
            summary.removed,
            summary.skipped,
            len(summary.errors),
        )
        if job_id:
            registry.update(job_id, state="completed", result=summary.as_dict())

    return summary.as_dict()


def purge_library_index(session: Session, library_id: int) -> int:
    """Soft-delete every indexed file for a library and trash now-empty models.

    Used when a library is removed. NAS bytes are never touched. Returns the
    number of files trashed."""
    now = utcnow()
    files = session.exec(
        select(File).where(File.external_library_id == library_id, live(File))
    ).all()
    affected_models: set[int] = set()
    for f in files:
        f.deleted_at = now
        session.add(f)
        if f.model_id is not None:
            affected_models.add(f.model_id)
    session.commit()

    for model_id in affected_models:
        remaining = session.exec(
            select(File).where(File.model_id == model_id, live(File))
        ).first()
        if remaining is None:
            model = session.get(Model, model_id)
            if model is not None and model.deleted_at is None:
                model.deleted_at = now
                model.updated_at = now
                session.add(model)
    session.commit()
    return len(files)


def libraries_due_for_scan(session: Session) -> list[int]:
    """IDs of enabled libraries whose scan interval has elapsed (or never ran)."""
    now = utcnow()
    due: list[int] = []
    for lib in session.exec(select(ExternalLibrary).where(ExternalLibrary.enabled == True)).all():  # noqa: E712
        if lib.id is None:
            continue
        if lib.last_scan_status == ExternalLibraryScanStatus.RUNNING:
            continue
        if lib.last_scanned_at is None:
            due.append(lib.id)
            continue
        elapsed_min = (now - lib.last_scanned_at).total_seconds() / 60.0
        if elapsed_min >= lib.scan_interval_minutes:
            due.append(lib.id)
    return due
