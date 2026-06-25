"""API coverage for the Spoolman integration (superuser-only)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_requires_superuser(client: TestClient):
    assert client.get("/api/v1/spoolman").status_code == 401


def test_status_defaults_disabled(client: TestClient, auth_headers):
    body = client.get("/api/v1/spoolman", headers=auth_headers).json()
    assert body["enabled"] is False
    assert body["base_url"] is None
    assert body["has_api_key"] is False
    # Disabled means no network probe runs.
    assert body["connected"] is False


def test_config_roundtrip_and_masks_key(client: TestClient, auth_headers):
    resp = client.put(
        "/api/v1/spoolman",
        json={"base_url": "http://spoolman.local:7912", "api_key": "secret"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_url"] == "http://spoolman.local:7912"
    # The key itself is never returned; only its presence.
    assert body["has_api_key"] is True
    assert "secret" not in resp.text


def test_update_preserves_key_when_masked(client: TestClient, auth_headers):
    client.put(
        "/api/v1/spoolman",
        json={"base_url": "http://spoolman.local:7912", "api_key": "secret"},
        headers=auth_headers,
    )
    # Re-sending the mask must not wipe the stored key.
    client.put(
        "/api/v1/spoolman",
        json={"base_url": "http://spoolman.local:7912", "api_key": "********"},
        headers=auth_headers,
    )
    body = client.get("/api/v1/spoolman", headers=auth_headers).json()
    assert body["has_api_key"] is True


def test_spools_empty_when_disabled(client: TestClient, auth_headers):
    # Even with a base URL set, a disabled integration returns no inventory and
    # makes no network call.
    client.put(
        "/api/v1/spoolman",
        json={"base_url": "http://spoolman.local:7912"},
        headers=auth_headers,
    )
    resp = client.get("/api/v1/spoolman/spools", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_enable_toggle(client: TestClient, auth_headers):
    client.put("/api/v1/spoolman", json={"enabled": True}, headers=auth_headers)
    assert client.get("/api/v1/spoolman", headers=auth_headers).json()["enabled"] is True
