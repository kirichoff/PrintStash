"""URL + ZIP import coverage driven by *real* benchy testdata and real-world
model-host URLs (Printables / MakerWorld).

These exercise the ``/ingest/url`` and ``/ingest/archive`` surfaces end-to-end:

* A direct-file URL import (as if Printables served the STL directly) ingests
  the real ``testdata/benchy`` mesh and records the source URL on the model.
* A ``.zip`` URL import (as if MakerWorld served a project bundle) resolves to
  an archive manifest, then selective import creates one model per 3D file and
  propagates the source URL to each.
* A plain ``.zip`` upload built from the real testdata files imports the
  importable entries (and skips unsupported ones like ``.bgcode``/``.txt``).

The network is never touched: ``download_to_staging`` is mocked to stage a
*copy* of the real testdata file (ingestion *moves* staged blobs into the
vault, so the originals under ``testdata/`` are never disturbed), the SSRF
guard is mocked so the real public hosts don't require DNS in CI, and — for the
model-*page* URLs — ``resolve_page_url`` is mocked so the host download APIs
(Printables GraphQL, MakerWorld) aren't called. The provided URLs are still
threaded through as the real ``source_url`` values. Resolver internals are
covered separately in ``test_import_resolvers.py``.
"""

from __future__ import annotations

import io
import threading
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.core.http_client as http_client
from app.core.config import _overlay, settings
from app.db.models import Collection, File, FileType, Model
from app.services import importer

# --------------------------------------------------------------------------- #
# Real fixtures + real-world URLs
# --------------------------------------------------------------------------- #
TESTDATA = Path(__file__).resolve().parents[2] / "testdata"

BENCHY_STL = TESTDATA / "benchy" / "3dbenchy.stl"
BENCHY_GCODE_A = TESTDATA / "benchy" / "3dbenchy_PLA_1h12m.gcode"
BENCHY_GCODE_B = TESTDATA / "benchy" / "3dbenchy_PLA_1h13m.gcode"
BENCHY_BGCODE = TESTDATA / "benchy" / "BenchyRules_PLA_14m.bgcode"

# The exact model-page URLs a user would paste from each host.
PRINTABLES_URL = "https://www.printables.com/model/3161-3d-benchy"
MAKERWORLD_URL = (
    "https://makerworld.com/es/models/1123776-original-3d-benchy"
    "?from=search#profileId-1355120"
)


def _requires(*paths: Path):
    missing = [p for p in paths if not p.exists()]
    return pytest.mark.skipif(
        bool(missing), reason=f"missing real fixture(s): {missing}"
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _configure_storage(tmp_path: Path) -> None:
    _overlay["data_dir"] = tmp_path / "files"
    _overlay["thumb_dir"] = tmp_path / "thumbs"
    _overlay["staging_dir"] = tmp_path / "staging"
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)


def _stage_bytes(data: bytes, suffix: str) -> Path:
    """Drop bytes into the staging incoming dir as a real download would."""
    staged = settings.incoming_dir / f"{uuid.uuid4().hex}{suffix}"
    staged.write_bytes(data)
    return staged


def _fake_download(staged: Path, original_filename: str) -> AsyncMock:
    """Mock for ``download_to_staging`` that yields an already-staged file."""

    async def _dl(url: str):  # signature mirrors the real coroutine
        return staged, original_filename

    return AsyncMock(side_effect=_dl)


def _patch_resolver(resolved_url: str | None):
    """Patch page resolution so model-page URLs never hit the real host APIs.

    ``resolved_url`` is the direct download URL the resolver would return for a
    recognised page; ``None`` mimics an unrecognised host (direct download).
    """
    return patch(
        "app.api.v1.ingest.import_resolvers.resolve_page_url",
        new=AsyncMock(return_value=resolved_url),
    )


def _benchy_zip_bytes(*sources: Path) -> bytes:
    """Build a real .zip from testdata files, preserving their names."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in sources:
            zf.writestr(f"3DBenchy/{src.name}", src.read_bytes())
        zf.writestr("3DBenchy/README.txt", b"original 3DBenchy by CreativeTools")
    return buf.getvalue()


def _job(client: TestClient, resp, headers: dict[str, str]) -> dict:
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    job = client.get(f"/api/v1/ingest/jobs/{job_id}", headers=headers)
    assert job.status_code == 200, job.text
    return job.json()


# --------------------------------------------------------------------------- #
# A real loopback HTTP server, so the download path runs for real
# --------------------------------------------------------------------------- #
_REDIRECTS = {301, 302, 303, 307, 308}


@pytest.fixture
def http_server() -> Iterator[tuple[str, dict[str, dict]]]:
    """Serve registered routes from a real socket on 127.0.0.1.

    Yields ``(base_url, routes)``; tests register ``routes[path] = {...}`` with
    optional ``status``, ``headers`` and ``body`` keys.
    """
    routes: dict[str, dict] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # silence stderr access logs
            pass

        def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
            spec = routes.get(self.path)
            if spec is None:
                self.send_response(404)
                self.end_headers()
                return
            status = spec.get("status", 200)
            body: bytes = spec.get("body", b"")
            self.send_response(status)
            for key, value in spec.get("headers", {}).items():
                self.send_header(key, value)
            if status not in _REDIRECTS:
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body and status not in _REDIRECTS:
                self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base, routes
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def _fresh_http_client() -> Iterator[None]:
    """Force the process-wide httpx client to rebind to the test's event loop."""
    http_client._http_client = None
    yield
    http_client._http_client = None


# --------------------------------------------------------------------------- #
# download_to_staging — exercised against a real server (no mocking)
# --------------------------------------------------------------------------- #
@_requires(BENCHY_STL)
@pytest.mark.asyncio
async def test_download_to_staging_fetches_real_file(
    tmp_path: Path, http_server: tuple[str, dict[str, dict]]
) -> None:
    _configure_storage(tmp_path)
    base, routes = http_server
    stl_bytes = BENCHY_STL.read_bytes()
    routes["/download"] = {
        "headers": {
            "Content-Type": "model/stl",
            "Content-Disposition": 'attachment; filename="3dbenchy.stl"',
        },
        "body": stl_bytes,
    }

    # Only the SSRF guard's IP classification is relaxed; the rest of the
    # download (real httpx stream, header parsing, disk write) runs for real.
    with patch.object(importer, "_is_public_ip", return_value=True):
        staged, filename = await importer.download_to_staging(f"{base}/download")

    assert filename == "3dbenchy.stl"
    assert staged.exists()
    assert staged.read_bytes() == stl_bytes
    assert staged.parent == settings.incoming_dir
    assert staged.suffix == ".stl"


@pytest.mark.asyncio
async def test_download_to_staging_follows_redirect(
    tmp_path: Path, http_server: tuple[str, dict[str, dict]]
) -> None:
    _configure_storage(tmp_path)
    base, routes = http_server
    routes["/start"] = {"status": 302, "headers": {"Location": "/final.stl"}}
    routes["/final.stl"] = {"headers": {"Content-Type": "model/stl"}, "body": b"solid x\nendsolid x\n"}

    with patch.object(importer, "_is_public_ip", return_value=True):
        staged, filename = await importer.download_to_staging(f"{base}/start")

    # Filename falls back to the final URL's path component.
    assert filename == "final.stl"
    assert staged.read_bytes() == b"solid x\nendsolid x\n"


@pytest.mark.asyncio
async def test_download_to_staging_enforces_size_limit(
    tmp_path: Path, http_server: tuple[str, dict[str, dict]]
) -> None:
    _configure_storage(tmp_path)
    _overlay["max_upload_mb"] = 1  # 1 MiB cap
    base, routes = http_server
    routes["/big.stl"] = {"body": b"\0" * (2 * 1024 * 1024)}  # 2 MiB

    incoming_before = set(settings.incoming_dir.iterdir())
    with patch.object(importer, "_is_public_ip", return_value=True):
        with pytest.raises(importer.ImportError_) as exc:
            await importer.download_to_staging(f"{base}/big.stl")

    assert str(exc.value) == "download_too_large"
    # The oversized partial download was cleaned up, not left in staging.
    assert set(settings.incoming_dir.iterdir()) == incoming_before


@pytest.mark.asyncio
async def test_download_to_staging_rejects_private_host(
    tmp_path: Path, http_server: tuple[str, dict[str, dict]]
) -> None:
    """Without relaxing the guard, the loopback server is refused (real SSRF)."""
    _configure_storage(tmp_path)
    base, routes = http_server
    routes["/download"] = {"body": b"data"}

    with pytest.raises(importer.ImportError_) as exc:
        await importer.download_to_staging(f"{base}/download")
    assert str(exc.value) == "url_target_not_public"


# --------------------------------------------------------------------------- #
# Full /ingest/url path — real download + real ingest, only SSRF relaxed
# --------------------------------------------------------------------------- #
@_requires(BENCHY_STL)
def test_ingest_url_downloads_and_ingests_for_real(
    tmp_path: Path,
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
    http_server: tuple[str, dict[str, dict]],
) -> None:
    _configure_storage(tmp_path)
    base, routes = http_server
    routes["/3dbenchy.stl"] = {
        "headers": {"Content-Type": "model/stl"},
        "body": BENCHY_STL.read_bytes(),
    }
    url = f"{base}/3dbenchy.stl"

    with patch.object(importer, "_is_public_ip", return_value=True):
        payload = _job(
            client,
            client.post(
                "/api/v1/ingest/url",
                headers=auth_headers,
                json={"url": url},
            ),
            auth_headers,
        )

    assert payload["state"] == "completed", payload
    model = db_session.get(Model, payload["model_id"])
    assert model is not None and model.source_url == url
    file_row = db_session.exec(select(File).where(File.model_id == model.id)).first()
    assert file_row is not None and file_row.file_type == FileType.STL
    assert file_row.size_bytes == BENCHY_STL.stat().st_size


# --------------------------------------------------------------------------- #
# URL import — direct file (Printables)
# --------------------------------------------------------------------------- #
@_requires(BENCHY_STL)
def test_import_real_benchy_from_printables_url_records_source(
    tmp_path: Path,
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
) -> None:
    _configure_storage(tmp_path)
    staged = _stage_bytes(BENCHY_STL.read_bytes(), ".stl")

    with (
        patch("app.api.v1.ingest.importer.validate_public_url", return_value=None),
        # The Printables page resolves to a direct STL link server-side.
        _patch_resolver("https://files.printables.test/3dbenchy.stl"),
        patch(
            "app.api.v1.ingest.importer.download_to_staging",
            new=_fake_download(staged, "3dbenchy.stl"),
        ),
    ):
        payload = _job(
            client,
            client.post(
                "/api/v1/ingest/url",
                headers=auth_headers,
                json={"url": PRINTABLES_URL},
            ),
            auth_headers,
        )

    assert payload["state"] == "completed", payload
    assert payload["model_id"] is not None
    model = db_session.get(Model, payload["model_id"])
    assert model is not None
    # The paste-able model-page URL is preserved verbatim as the source.
    assert model.source_url == PRINTABLES_URL

    file_row = db_session.exec(
        select(File).where(File.model_id == model.id)
    ).first()
    assert file_row is not None and file_row.file_type == FileType.STL
    assert file_row.size_bytes == BENCHY_STL.stat().st_size
    # The staged copy was moved into the vault; the testdata original is intact.
    assert BENCHY_STL.exists()


@_requires(BENCHY_STL)
def test_import_from_url_honours_model_name_override(
    tmp_path: Path,
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
) -> None:
    """A ``model_name`` supplied to /ingest/url names the resulting model rather
    than falling back to the download's filename stem."""
    _configure_storage(tmp_path)
    staged = _stage_bytes(BENCHY_STL.read_bytes(), ".stl")

    with (
        patch("app.api.v1.ingest.importer.validate_public_url", return_value=None),
        _patch_resolver("https://files.printables.test/3dbenchy.stl"),
        patch(
            "app.api.v1.ingest.importer.download_to_staging",
            new=_fake_download(staged, "3dbenchy.stl"),
        ),
    ):
        payload = _job(
            client,
            client.post(
                "/api/v1/ingest/url",
                headers=auth_headers,
                json={"url": PRINTABLES_URL, "model_name": "Original 3DBenchy"},
            ),
            auth_headers,
        )

    assert payload["state"] == "completed", payload
    model = db_session.get(Model, payload["model_id"])
    assert model is not None
    assert model.name == "Original 3DBenchy"


# --------------------------------------------------------------------------- #
# URL import — .zip bundle (MakerWorld)
# --------------------------------------------------------------------------- #
@_requires(BENCHY_STL, BENCHY_GCODE_A)
def test_import_real_benchy_zip_from_makerworld_url(
    tmp_path: Path,
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
) -> None:
    _configure_storage(tmp_path)
    zip_bytes = _benchy_zip_bytes(BENCHY_STL, BENCHY_GCODE_A)
    staged = _stage_bytes(zip_bytes, ".zip")

    with (
        patch("app.api.v1.ingest.importer.validate_public_url", return_value=None),
        # The MakerWorld page resolves to a direct .zip bundle link server-side.
        _patch_resolver("https://makerworld.test/instance/123/f3mf.zip"),
        patch(
            "app.api.v1.ingest.importer.download_to_staging",
            new=_fake_download(staged, "3d-benchy.zip"),
        ),
    ):
        manifest = _job(
            client,
            client.post(
                "/api/v1/ingest/url",
                headers=auth_headers,
                json={"url": MAKERWORLD_URL},
            ),
            auth_headers,
        )

    # A .zip URL resolves to an archive manifest rather than importing directly.
    assert manifest["state"] == "completed", manifest
    result = manifest["result"]
    assert result["kind"] == "archive_manifest"
    archive_id = result["archive_id"]
    importable = sorted(e["name"] for e in result["entries"] if e["file_type"])
    assert importable == ["3DBenchy/3dbenchy.stl", "3DBenchy/3dbenchy_PLA_1h12m.gcode"]

    payload = _job(
        client,
        client.post(
            f"/api/v1/ingest/archive/{archive_id}/select",
            headers=auth_headers,
            json={"names": importable},
        ),
        auth_headers,
    )
    assert payload["state"] == "completed", payload
    assert payload["result"]["imported"] == 2

    # Both files landed as their own models, each carrying the MakerWorld URL.
    models = db_session.exec(select(Model).where(Model.source_url == MAKERWORLD_URL)).all()
    assert len(models) == 2
    assert {FileType.STL, FileType.GCODE} == {
        db_session.exec(select(File).where(File.model_id == m.id)).first().file_type
        for m in models
    }


# --------------------------------------------------------------------------- #
# ZIP upload — built from real testdata files
# --------------------------------------------------------------------------- #
@_requires(BENCHY_GCODE_A, BENCHY_GCODE_B)
def test_import_zip_built_from_testdata_benchy_files(
    tmp_path: Path,
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
) -> None:
    _configure_storage(tmp_path)
    # Include a .bgcode (unsupported) and a README so we assert they're skipped.
    sources = [BENCHY_GCODE_A, BENCHY_GCODE_B]
    if BENCHY_BGCODE.exists():
        sources.append(BENCHY_BGCODE)
    zip_bytes = _benchy_zip_bytes(*sources)

    manifest = client.post(
        "/api/v1/ingest/archive",
        headers=auth_headers,
        files={"file": ("benchy-bundle.zip", zip_bytes, "application/zip")},
    )
    assert manifest.status_code == 200, manifest.text
    body = manifest.json()
    archive_id = body["archive_id"]
    importable = sorted(e["name"] for e in body["entries"] if e["file_type"])
    # Only the two real g-code files are importable; .bgcode and .txt are not.
    assert importable == [
        "3DBenchy/3dbenchy_PLA_1h12m.gcode",
        "3DBenchy/3dbenchy_PLA_1h13m.gcode",
    ]

    payload = _job(
        client,
        client.post(
            f"/api/v1/ingest/archive/{archive_id}/select",
            headers=auth_headers,
            json={"names": importable},
        ),
        auth_headers,
    )
    assert payload["state"] == "completed", payload
    assert payload["result"]["imported"] == 2

    # Both g-code files were grouped under one auto-created collection named
    # after the archive.
    collection = db_session.exec(
        select(Collection).where(Collection.name.ilike("%benchy-bundle%"))  # type: ignore[attr-defined]
    ).first()
    assert collection is not None
    models = db_session.exec(
        select(Model).where(Model.collection_id == collection.id)
    ).all()
    assert len(models) == 2


# --------------------------------------------------------------------------- #
# URL import — pasting a model *page* (HTML), not a direct file
# --------------------------------------------------------------------------- #
def test_import_url_unrecognised_host_html_fails_gracefully(
    tmp_path: Path,
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """A direct URL on an unrecognised host that resolves to HTML (no usable
    suffix) is rejected cleanly as ``url_not_a_direct_file`` rather than
    crashing the job. Resolution returns ``None`` for the unknown host, so the
    raw URL is downloaded as-is."""
    _configure_storage(tmp_path)
    staged = _stage_bytes(b"<!doctype html><title>3DBenchy</title>", ".bin")

    with (
        patch("app.api.v1.ingest.importer.validate_public_url", return_value=None),
        _patch_resolver(None),  # unrecognised host -> treated as a direct URL
        patch(
            "app.api.v1.ingest.importer.download_to_staging",
            new=_fake_download(staged, "some-page"),
        ),
    ):
        payload = _job(
            client,
            client.post(
                "/api/v1/ingest/url",
                headers=auth_headers,
                json={"url": "https://example.test/some-page"},
            ),
            auth_headers,
        )

    assert payload["state"] == "failed", payload
    assert payload["error"] == "url_not_a_direct_file"
    # The unusable download was cleaned out of staging.
    assert not staged.exists()


def test_import_url_unresolvable_page_reports_host_error(
    tmp_path: Path,
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """When a recognised model page can't be resolved to a download link, the
    job fails with the host-specific code (not a generic crash), and nothing is
    downloaded."""
    _configure_storage(tmp_path)

    download = _fake_download(_stage_bytes(b"x", ".bin"), "unused")
    with (
        patch("app.api.v1.ingest.importer.validate_public_url", return_value=None),
        patch(
            "app.api.v1.ingest.import_resolvers.resolve_page_url",
            new=AsyncMock(side_effect=importer.ImportError_("printables_resolve_failed")),
        ),
        patch("app.api.v1.ingest.importer.download_to_staging", new=download),
    ):
        payload = _job(
            client,
            client.post(
                "/api/v1/ingest/url",
                headers=auth_headers,
                json={"url": PRINTABLES_URL},
            ),
            auth_headers,
        )

    assert payload["state"] == "failed", payload
    assert payload["error"] == "printables_resolve_failed"
    # Resolution failed before any download was attempted.
    download.assert_not_awaited()
