
def _3mf_extract_docs_and_plates(
    staged_path: Path,
    collection: Optional[str],
    session_factory: SessionFactory,
    model_id: int,
) -> None:
    """Extract Description XML, .md/.txt docs, and plate previews from a 3MF archive.

    Saves Description as a markdown document in the model's collection.
    Extracts plate_*.png / top_*.png as image files attached to the model.
    """
    import zipfile, html, re as _re
    import xml.etree.ElementTree as ET
    from app.db.models import Document, DocumentKind, File as FileModel, FileType
    from sqlmodel import select

    if not staged_path or not staged_path.exists():
        return

    coll_id = _resolve_coll_id(collection, session_factory)
    plate_images: list[tuple[str, bytes]] = []
    model_xml_description: Optional[str] = None

    try:
        with zipfile.ZipFile(staged_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                fname = info.filename.lower()
                suffix = Path(info.filename).suffix.lower()

                # .md / .txt / .pdf
                if suffix in (".md", ".markdown", ".txt", ".pdf"):
                    _create_doc_from_3mf(
                        zf, info, coll_id, session_factory,
                    )
                # Plate previews
                elif suffix == ".png" and (
                    fname.startswith("metadata/plate_") or
                    fname.startswith("metadata/top_") or
                    fname.startswith("metadata/pick_")
                ):
                    plate_images.append((info.filename, zf.read(info)))
                # 3dmodel.model Description XML
                elif fname.endswith("3dmodel.model"):
                    try:
                        xml_data = zf.read(info)
                        root = ET.fromstring(xml_data)
                        ns = {"": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
                        for meta in root.findall(".//metadata", ns):
                            name = meta.get("name", "")
                            if name == "Description" and meta.text and meta.text.strip():
                                model_xml_description = meta.text.strip()
                                break
                    except Exception:
                        pass

        # Save Description as document
        if model_xml_description and coll_id:
            desc_text = html.unescape(model_xml_description)
            for br in ("<br>", "<br/>", "<br />"):
                desc_text = desc_text.replace(br, "\n")
            desc_text = _re.sub(r'<[^>]+>', '', desc_text)
            desc_text = html.unescape(desc_text)

            with session_factory() as session:
                existing = session.exec(
                    select(Document).where(
                        Document.name == "Model Description",
                        Document.collection_id == coll_id,
                        Document.deleted_at.is_(None),
                    )
                ).first()
                if not existing:
                    doc = Document(
                        name="Model Description",
                        kind=DocumentKind.MARKDOWN,
                        collection_id=coll_id,
                        body=desc_text.strip(),
                    )
                    session.add(doc)
                    session.commit()
                    logger.info(
                        "ingest_3mf: saved description from 3dmodel.model (%d chars)",
                        len(desc_text),
                    )

        # Save plate previews as image files attached to the model
        if plate_images and model_id:
            with session_factory() as session:
                from app.services.storage_backend import get_backend
                from app.core.time import utcnow

                backend = get_backend()
                for rel_path, img_data in plate_images:
                    stem = Path(rel_path).stem
                    plate_file = FileModel(
                        model_id=model_id,
                        original_filename=Path(rel_path).name,
                        file_type=FileType.IMAGE,
                        size_bytes=len(img_data),
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                    session.add(plate_file)
                    session.commit()
                    session.refresh(plate_file)

                    thumb_key = backend.thumbnail_key(plate_file.id)
                    # Convert PNG to WebP for storage
                    try:
                        from PIL import Image
                        import io as _io
                        img = Image.open(_io.BytesIO(img_data))
                        webp_buf = _io.BytesIO()
                        img.save(webp_buf, "WEBP", lossless=True)
                        webp_data = webp_buf.getvalue()
                        backend.write_bytes(webp_data, thumb_key)
                    except Exception:
                        backend.write_bytes(img_data, thumb_key)

                    # Set as model thumbnail if none set
                    model = session.get(Model, model_id)
                    if model and not model.thumbnail_path:
                        model.thumbnail_path = thumb_key
                        model.thumbnail_file_id = plate_file.id
                        session.add(model)
                        session.commit()

                logger.info(
                    "ingest_3mf: saved %d plate images for model %d",
                    len(plate_images), model_id,
                )

    except Exception:
        logger.info(
            "ingest_3mf: extract failed for %s (non-fatal)",
            staged_path.name, exc_info=True,
        )


def _create_doc_from_3mf(
    zf: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    coll_id: Optional[int],
    session_factory: SessionFactory,
) -> None:
    """Extract a single .md/.txt/.pdf from 3MF and save as collection document."""
    from app.db.models import Document, DocumentKind

    if coll_id is None:
        return
    suffix = Path(info.filename).suffix.lower()
    try:
        data = zf.read(info)
    except Exception:
        return
    filename = Path(info.filename).name
    name = filename.rsplit(".", 1)[0][:128]
    kind = (
        DocumentKind.MARKDOWN if suffix in (".md", ".markdown", ".txt")
        else DocumentKind.PDF if suffix == ".pdf"
        else DocumentKind.OTHER
    )
    with session_factory() as session:
        doc = Document(
            name=name, kind=kind, collection_id=coll_id,
        )
        if kind is DocumentKind.MARKDOWN:
            doc.body = data.decode("utf-8", errors="replace")
        doc.size_bytes = len(data)
        session.add(doc)
        session.commit()


def _resolve_coll_id(
    collection: Optional[str],
    session_factory: SessionFactory,
) -> Optional[int]:
    from app.services import taxonomy

    if not collection:
        return None
    with session_factory() as session:
        col = taxonomy.resolve_or_create_collection(session, collection)
        return col.id if col else None
