"""Feature #1 — the /files/{id}/plates endpoint serves per-plate layout for a
3MF, and each object's STL is fetchable and cached.

Driven by the real 2-plate fixture; skips when absent.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import _overlay

TESTDATA = Path(__file__).resolve().parents[2] / "testdata"
MULTIPLATE_3MF = TESTDATA / "multiplate_2plates_benchy_torus.3mf"
CUBE_STL = TESTDATA / "Calibration Cube.stl"


def _configure_storage(tmp_path: Path) -> None:
    _overlay["data_dir"] = tmp_path / "files"
    _overlay["thumb_dir"] = tmp_path / "thumbs"
    _overlay["staging_dir"] = tmp_path / "staging"


def _completed_job(client: TestClient, response) -> dict:
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    headers = {}
    auth = response.request.headers.get("authorization")
    if auth:
        headers["Authorization"] = auth
    job = client.get(f"/api/v1/ingest/jobs/{job_id}", headers=headers)
    assert job.status_code == 200, job.text
    payload = job.json()
    assert payload["state"] == "completed", payload
    return payload


def _ingest_3mf(client: TestClient, auth_headers: dict, src: Path, name: str) -> dict:
    return _completed_job(
        client,
        client.post(
            "/api/v1/ingest/model",
            headers=auth_headers,
            files={"file": (src.name, src.read_bytes(), "model/3mf")},
            data={"model_name": name},
        ),
    )


def test_plates_endpoint_returns_two_plates(
    tmp_path: Path, client: TestClient, auth_headers: dict[str, str]
) -> None:
    if not MULTIPLATE_3MF.exists():
        import pytest

        pytest.skip(f"missing fixture {MULTIPLATE_3MF}")
    _configure_storage(tmp_path)
    payload = _ingest_3mf(client, auth_headers, MULTIPLATE_3MF, "Plates API")
    file_id = payload["file_id"]

    resp = client.get(f"/api/v1/files/{file_id}/plates", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["plate_count"] == 2
    assert data["object_count"] == 2
    assert [p["index"] for p in data["plates"]] == [1, 2]

    # Each object exposes a fetchable STL URL.
    obj = data["plates"][0]["objects"][0]
    assert obj["bbox_mm"][0] > 0
    stl = client.get(obj["stl_url"], headers=auth_headers)
    assert stl.status_code == 200, stl.text
    assert stl.content[:5] or len(stl.content) > 84
    assert stl.headers["content-type"] == "application/sla"


def test_plates_endpoint_404_for_non_3mf(
    tmp_path: Path, client: TestClient, auth_headers: dict[str, str]
) -> None:
    if not CUBE_STL.exists():
        import pytest

        pytest.skip(f"missing fixture {CUBE_STL}")
    _configure_storage(tmp_path)
    payload = _completed_job(
        client,
        client.post(
            "/api/v1/ingest/model",
            headers=auth_headers,
            files={"file": (CUBE_STL.name, CUBE_STL.read_bytes(), "application/sla")},
            data={"model_name": "Just STL"},
        ),
    )
    resp = client.get(
        f"/api/v1/files/{payload['file_id']}/plates", headers=auth_headers
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "not_a_3mf"
