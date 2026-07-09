"""The single source of truth for "which blobs does the database still own?".

Both the orphan-blob GC (``services.trash``) and the backup manifest
(``services.backup``) have to answer this question, and they must answer it
identically: a key the GC believes is orphaned gets deleted, and a key the
backup misses is silently absent from the archive. They used to census
``File.path`` alone, which made every Document blob look unowned.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.db.models import Document, File
from app.services.storage_backend import get_backend


def all_owned_blob_keys(session: Session) -> set[str]:
    """Every storage key a DB row lays claim to, across all owning tables.

    Trashed rows are included on purpose: their bytes must survive until the
    row is hard-deleted, otherwise restoring from trash yields an empty file.

    Derived artefacts (thumbnails, the STL cache) and readme/body images are
    absent because neither sweeper walks their prefixes — they live under
    ``thumb_dir`` locally and outside ``vault-data/files/`` on S3. Widening a
    walker to cover them means teaching this function to enumerate them first.
    """
    backend = get_backend()

    keys: set[str] = set(session.exec(select(File.path)).all())

    documents = session.exec(
        select(Document.id, Document.filename).where(Document.filename.is_not(None))  # type: ignore[union-attr]
    ).all()
    keys.update(
        backend.document_file_key(doc_id, filename) for doc_id, filename in documents
    )

    return keys
