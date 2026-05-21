"""Ingestion orchestrator — runs in a FastAPI BackgroundTask."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.db.models import File, FileType, Metadata, Model, ModelTagLink
from app.db.session import engine
from app.services import gcode_parser, storage, taxonomy, thumbnail
from app.services.hashing import sha256_file
from app.services.jobs import registry

logger = get_logger(__name__)


def _model_exists_with_slug(session: Session, slug: str) -> bool:
    stmt = select(Model).where(Model.slug == slug)
    return session.exec(stmt).first() is not None


def _next_version_for_model(session: Session, model_id: int) -> int:
    stmt = select(File).where(File.model_id == model_id)
    files = session.exec(stmt).all()
    if not files:
        return 1
    return max(f.version for f in files) + 1


def _apply_taxonomy(
    session: Session,
    model: Model,
    category: Optional[str],
    tags_raw: Optional[str],
    *,
    overwrite_category: bool = False,
) -> None:
    """Resolve & attach category + tags. Idempotent."""
    if category:
        cat = taxonomy.resolve_or_create_category(session, category)
        if cat is not None:
            if overwrite_category or model.category_id is None:
                model.category_id = cat.id
            if overwrite_category or not model.category:
                model.category = cat.path
            session.add(model)
            session.commit()

    tag_names = taxonomy.parse_tag_input(tags_raw)
    if tag_names:
        new_tags = taxonomy.resolve_or_create_tags(session, tag_names)
        existing_ids = {
            row.tag_id
            for row in session.exec(
                select(ModelTagLink).where(ModelTagLink.model_id == model.id)
            ).all()
        }
        for tag in new_tags:
            if tag.id not in existing_ids:
                session.add(ModelTagLink(model_id=model.id, tag_id=tag.id))
        # Mirror into legacy tags_csv for any older consumers.
        all_tag_names = sorted({t.name for t in new_tags} | set(
            taxonomy.parse_tag_input(model.tags_csv)
        ))
        model.tags_csv = ",".join(all_tag_names) if all_tag_names else None
        session.add(model)
        session.commit()


def ingest_orca_gcode(
    *,
    job_id: str,
    staged_path: Path,
    original_filename: str,
    model_name: str,
    category: Optional[str],
    tags: Optional[str],
    source_hash: Optional[str],
) -> None:
    """Background task: process a staged G-code file through the full pipeline."""
    logger.info("ingest[%s] start file=%s", job_id, original_filename)
    registry.update(job_id, state="running")

    try:
        # 1. Hash the blob.
        blob_hash = sha256_file(staged_path)
        logger.info("ingest[%s] sha256=%s", job_id, blob_hash)

        # 2. Parse G-code metadata + thumbnail.
        meta = gcode_parser.parse(staged_path)
        thumb_bytes = thumbnail.extract(staged_path)

        # 3. Determine dedup key.
        dedup_hash = (source_hash or blob_hash).lower()

        with Session(engine) as session:
            # 4. Find or create Model.
            existing = session.exec(select(Model).where(Model.hash == dedup_hash)).first()

            if existing is None:
                base_slug = storage.slugify(model_name)
                slug = storage.ensure_unique_slug(
                    base_slug, lambda s: _model_exists_with_slug(session, s)
                )
                model = Model(name=model_name, slug=slug, hash=dedup_hash)
                session.add(model)
                session.commit()
                session.refresh(model)
                logger.info("ingest[%s] new model id=%s slug=%s", job_id, model.id, model.slug)
            else:
                model = existing
                model.updated_at = datetime.utcnow()
                session.add(model)
                session.commit()
                session.refresh(model)
                logger.info("ingest[%s] dedup hit model_id=%s", job_id, model.id)

            assert model.id is not None

            _apply_taxonomy(session, model, category, tags)

            # 5. Determine version & destination path.
            version = _next_version_for_model(session, model.id)
            dest = storage.canonical_blob_path(model.slug, version, original_filename)

            # 6. Move blob into canonical location.
            storage.move_file(staged_path, dest)
            size_bytes = dest.stat().st_size

            # 7. Insert File row.
            file_row = File(
                model_id=model.id,
                path=str(dest),
                original_filename=original_filename,
                file_type=FileType.GCODE,
                version=version,
                size_bytes=size_bytes,
                sha256=blob_hash,
            )
            session.add(file_row)
            session.commit()
            session.refresh(file_row)
            assert file_row.id is not None

            # 8. Persist thumbnail.
            if thumb_bytes:
                thumb_path = storage.thumbnail_path_for(file_row.id)
                thumb_path.parent.mkdir(parents=True, exist_ok=True)
                thumb_path.write_bytes(thumb_bytes)
                if not model.thumbnail_path:
                    model.thumbnail_path = str(thumb_path)
                    model.thumbnail_file_id = file_row.id
                    session.add(model)
                    session.commit()

            # 9. Insert Metadata row.
            md = Metadata(file_id=file_row.id, **meta)
            session.add(md)
            session.commit()

            registry.update(
                job_id,
                state="completed",
                model_id=model.id,
                file_id=file_row.id,
            )
            logger.info(
                "ingest[%s] done model_id=%s file_id=%s v=%s",
                job_id, model.id, file_row.id, version,
            )

    except Exception as exc:  # noqa: BLE001 — top-level task boundary
        logger.exception("ingest[%s] failed: %s", job_id, exc)
        registry.update(job_id, state="failed", error=str(exc))


def ingest_mesh(
    *,
    job_id: str,
    staged_path: Path,
    original_filename: str,
    model_name: str,
    category: Optional[str],
    tags: Optional[str],
    file_type: FileType,
    source_hash: Optional[str],
) -> None:
    """Background task: process a staged mesh file (STL/3MF/OBJ) through the full pipeline."""
    from app.services import mesh_processing

    logger.info("ingest[%s] start mesh file=%s", job_id, original_filename)
    registry.update(job_id, state="running")

    try:
        blob_hash = sha256_file(staged_path)
        logger.info("ingest[%s] sha256=%s", job_id, blob_hash)

        geometry = mesh_processing.extract_geometry(staged_path)
        thumb_bytes = mesh_processing.render_thumbnail(staged_path)
        if thumb_bytes is None:
            logger.warning("ingest[%s] mesh thumbnail render returned None", job_id)
        else:
            logger.info("ingest[%s] rendered mesh thumbnail (%d bytes)", job_id, len(thumb_bytes))

        dedup_hash = (source_hash or blob_hash).lower()

        with Session(engine) as session:
            existing = session.exec(select(Model).where(Model.hash == dedup_hash)).first()

            if existing is None:
                base_slug = storage.slugify(model_name)
                slug = storage.ensure_unique_slug(
                    base_slug, lambda s: _model_exists_with_slug(session, s)
                )
                model = Model(name=model_name, slug=slug, hash=dedup_hash)
                session.add(model)
                session.commit()
                session.refresh(model)
                logger.info("ingest[%s] new model id=%s slug=%s", job_id, model.id, model.slug)
            else:
                model = existing
                model.updated_at = datetime.utcnow()
                session.add(model)
                session.commit()
                session.refresh(model)
                logger.info("ingest[%s] dedup hit model_id=%s", job_id, model.id)

            assert model.id is not None

            _apply_taxonomy(session, model, category, tags)

            version = _next_version_for_model(session, model.id)
            dest = storage.canonical_blob_path(model.slug, version, original_filename)
            storage.move_file(staged_path, dest)
            size_bytes = dest.stat().st_size

            file_row = File(
                model_id=model.id,
                path=str(dest),
                original_filename=original_filename,
                file_type=file_type,
                version=version,
                size_bytes=size_bytes,
                sha256=blob_hash,
            )
            session.add(file_row)
            session.commit()
            session.refresh(file_row)
            assert file_row.id is not None

            if thumb_bytes:
                thumb_path = storage.thumbnail_path_for(file_row.id)
                thumb_path.parent.mkdir(parents=True, exist_ok=True)
                thumb_path.write_bytes(thumb_bytes)
                # Mesh thumbnails always win over gcode ones (better view of part).
                model.thumbnail_path = str(thumb_path)
                model.thumbnail_file_id = file_row.id
                session.add(model)
                session.commit()

            md = Metadata(file_id=file_row.id, **geometry)
            session.add(md)
            session.commit()

            registry.update(
                job_id,
                state="completed",
                model_id=model.id,
                file_id=file_row.id,
            )
            logger.info(
                "ingest[%s] done model_id=%s file_id=%s v=%s",
                job_id, model.id, file_row.id, version,
            )

    except Exception as exc:  # noqa: BLE001 — top-level task boundary
        logger.exception("ingest[%s] failed: %s", job_id, exc)
        registry.update(job_id, state="failed", error=str(exc))
