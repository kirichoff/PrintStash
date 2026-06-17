"""R2 operations hardening: richer health, scan restart cleanup, metrics."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import _overlay
from app.db.models import ExternalLibrary, ExternalLibraryScanStatus
from app.services import external_library
from app.services.jobs import JobRegistry


# --- Item 1: richer /health output --------------------------------------------


def test_health_reports_jobs_and_external_libraries(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    components = body["components"]
    assert "jobs" in components
    assert "external_libraries" in components
    assert components["jobs"]["ok"] is True
    assert "counts" in components["jobs"]
    assert components["external_libraries"]["ok"] is True


def test_health_external_library_status_counts(
    client: TestClient, db_session: Session
) -> None:
    db_session.add(
        ExternalLibrary(
            name="nas",
            root_path="/mnt/nas",
            last_scan_status=ExternalLibraryScanStatus.RUNNING,
        )
    )
    db_session.commit()

    el = client.get("/api/v1/health").json()["components"]["external_libraries"]
    assert el["running"] == 1
    assert el["status_counts"].get("running") == 1
    # A genuinely running scan must not flip overall status to degraded.
    assert el["ok"] is True


# --- Item 2: background-scan restart cleanup ----------------------------------


def test_reset_orphaned_scans_recovers_stranded_library(db_session: Session) -> None:
    lib = ExternalLibrary(
        name="nas",
        root_path="/mnt/nas",
        enabled=True,
        scan_schedule="* * * * *",
        last_scanned_at=None,
        last_scan_status=ExternalLibraryScanStatus.RUNNING,
    )
    db_session.add(lib)
    db_session.commit()
    db_session.refresh(lib)

    # While stranded RUNNING, the scheduler skips it.
    assert lib.id not in external_library.libraries_due_for_scan(db_session)

    reset = external_library.reset_orphaned_scans(db_session)
    assert reset == 1

    db_session.refresh(lib)
    assert lib.last_scan_status == ExternalLibraryScanStatus.ERROR
    assert json.loads(lib.last_scan_summary)["error"] == "interrupted by restart"

    # Now it is eligible for scanning again.
    assert lib.id in external_library.libraries_due_for_scan(db_session)


def test_reset_orphaned_scans_noop_without_running(db_session: Session) -> None:
    db_session.add(
        ExternalLibrary(
            name="nas",
            root_path="/mnt/nas",
            last_scan_status=ExternalLibraryScanStatus.OK,
        )
    )
    db_session.commit()
    assert external_library.reset_orphaned_scans(db_session) == 0


# --- Item 3: Prometheus metrics -----------------------------------------------


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "printstash_app_info" in resp.text
    assert "printstash_http_request_duration_seconds" in resp.text


def test_metrics_counts_terminal_ingestion_jobs(client: TestClient) -> None:
    reg = JobRegistry()
    job_id = reg.create()
    reg.update(job_id, state="completed")

    body = client.get("/metrics").text
    assert 'printstash_ingestion_jobs_total{state="completed"}' in body


def test_metrics_token_enforced_when_set(client: TestClient) -> None:
    _overlay["metrics_token"] = "s3cr3t"
    try:
        assert client.get("/metrics").status_code == 401
        assert (
            client.get(
                "/metrics", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/metrics", headers={"Authorization": "Bearer s3cr3t"}
            ).status_code
            == 200
        )
    finally:
        _overlay.pop("metrics_token", None)
