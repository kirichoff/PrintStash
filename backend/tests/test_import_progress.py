from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import _overlay
from app.schemas.ingest import IngestJobStatus
from app.services.jobs import JobRegistry, safe_error, safe_item


@pytest.mark.parametrize(
    "stage",
    [
        "resolving",
        "downloading",
        "inspecting",
        "extracting",
        "hashing",
        "ingesting",
        "thumbnailing",
        "completed",
    ],
)
def test_registry_supports_every_import_stage(stage: str) -> None:
    jobs = JobRegistry()
    job_id = jobs.create(owner_user_id=7)
    jobs.update(job_id, stage=stage)  # type: ignore[arg-type]
    assert jobs.get(job_id).stage == stage  # type: ignore[union-attr]


def test_progress_keeps_total_unknown_until_discovery() -> None:
    jobs = JobRegistry()
    job_id = jobs.create(owner_user_id=7)
    jobs.update(job_id, state="running", stage="resolving", processed=0)
    assert jobs.get(job_id).total is None  # type: ignore[union-attr]

    jobs.update(job_id, stage="ingesting", total=3, processed=1)
    status = jobs.get(job_id)
    assert status is not None
    assert (status.processed, status.total) == (1, 3)


def test_partial_success_has_summary_and_safe_retry_details() -> None:
    jobs = JobRegistry()
    job_id = jobs.create(owner_user_id=7)
    jobs.update(
        job_id,
        state="completed",
        succeeded=2,
        deduplicated=1,
        skipped=1,
        failed=1,
        retryable=True,
        result={"errors": ["/srv/private/models/broken.stl: token=secret"]},
        failed_items=[
            {
                "name": "/srv/private/models/broken.stl",
                "reason": "read /srv/private/models/broken.stl?token=secret failed",
                "retryable": True,
            }
        ],
    )
    status = jobs.get(job_id)
    assert status is not None
    assert status.completion == "completed_with_warnings"
    assert status.failed_items[0].name == "broken.stl"
    assert "/srv/private" not in status.failed_items[0].reason
    assert "secret" not in status.failed_items[0].reason
    assert "/srv/private" not in str(status.result)
    assert "secret" not in str(status.result)


def test_complete_failure_is_distinct_from_partial_success() -> None:
    jobs = JobRegistry()
    job_id = jobs.create(owner_user_id=7)
    jobs.update(job_id, state="failed", error="download_failed", retryable=True)
    status = jobs.get(job_id)
    assert status is not None
    assert status.completion == "failed_before_import"
    assert status.succeeded == 0


def test_reconnect_listing_respects_owner_permissions() -> None:
    jobs = JobRegistry()
    own = jobs.create(owner_user_id=7)
    other = jobs.create(owner_user_id=8)
    assert [job.job_id for job in jobs.list_for_user(7)] == [own]
    assert {job.job_id for job in jobs.list_for_user(7, is_superuser=True)} == {
        own,
        other,
    }
    assert jobs.get(own).state == "pending"  # type: ignore[union-attr]


def test_display_sanitizers_hide_paths_credentials_and_control_characters() -> None:
    assert safe_item("/mnt/nas/private/Cube\n.stl") == "Cube.stl"
    error = safe_error("failed /mnt/nas/private/Cube.stl?api_key=hunter2")
    assert error is not None
    assert "/mnt/nas" not in error
    assert "hunter2" not in error


def test_progress_schema_rejects_unknown_stage() -> None:
    with pytest.raises(ValueError):
        IngestJobStatus(job_id="bad", state="running", stage="uploading")


def test_uploaded_zip_inspection_runs_as_reconnectable_job(
    tmp_path: Path, client: TestClient, auth_headers: dict[str, str]
) -> None:
    _overlay["staging_dir"] = tmp_path / "staging"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("models/cube.stl", b"solid cube\nendsolid cube\n")

    queued = client.post(
        "/api/v1/ingest/archive/inspect",
        headers=auth_headers,
        files={"file": ("models.zip", archive.getvalue(), "application/zip")},
    )
    assert queued.status_code == 202
    job_id = queued.json()["job_id"]
    status = client.get(f"/api/v1/ingest/jobs/{job_id}", headers=auth_headers)
    assert status.status_code == 200
    payload = status.json()
    assert payload["state"] == "completed"
    assert payload["stage"] == "completed"
    assert payload["result"]["kind"] == "archive_manifest"
    assert payload["result"]["entries"][0]["name"] == "cube.stl"
