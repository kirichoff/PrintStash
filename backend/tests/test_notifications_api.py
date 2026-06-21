"""API coverage for notification channel management (superuser-only)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create(client: TestClient, headers, **over):
    body = {
        "name": "My webhook",
        "target": "webhook",
        "config": {"url": "https://example.com/hook"},
        "events": ["print_completed", "print_failed"],
    }
    body.update(over)
    return client.post("/api/v1/notifications/channels", json=body, headers=headers)


def test_requires_superuser(client: TestClient):
    assert client.get("/api/v1/notifications").status_code == 401


def test_master_switch_roundtrip(client: TestClient, auth_headers):
    assert client.get("/api/v1/notifications", headers=auth_headers).json()["enabled"] is False
    client.put("/api/v1/notifications", json={"enabled": True}, headers=auth_headers)
    assert client.get("/api/v1/notifications", headers=auth_headers).json()["enabled"] is True


def test_create_masks_secret_url(client: TestClient, auth_headers):
    resp = _create(client, auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["config"]["url"] == "********"  # secret masked on read
    assert body["config_flags"]["has_url"] is True
    assert set(body["events"]) == {"print_completed", "print_failed"}


def test_update_preserves_secret_when_blank(client: TestClient, auth_headers):
    cid = _create(client, auth_headers).json()["id"]
    # Patch only the name; the secret URL must survive untouched.
    client.patch(
        f"/api/v1/notifications/channels/{cid}",
        json={"name": "Renamed"},
        headers=auth_headers,
    )
    # And re-sending the masked placeholder also preserves it.
    client.patch(
        f"/api/v1/notifications/channels/{cid}",
        json={"config": {"url": "********"}},
        headers=auth_headers,
    )
    # Verify by sending a test: a preserved URL renders/sends (mock the network).
    from unittest.mock import AsyncMock, MagicMock, patch

    resp = MagicMock(status_code=204, text="")
    fake = MagicMock(request=AsyncMock(return_value=resp))
    with patch("app.services.notifications.get_http_client", return_value=fake):
        out = client.post(
            f"/api/v1/notifications/channels/{cid}/test", headers=auth_headers
        ).json()
    assert out["ok"] is True
    sent_url = fake.request.call_args.args[1]
    assert sent_url == "https://example.com/hook"  # original secret, not the mask


def test_update_events_and_printer_scope(client: TestClient, auth_headers):
    cid = _create(client, auth_headers).json()["id"]
    body = client.patch(
        f"/api/v1/notifications/channels/{cid}",
        json={"events": ["printer_offline"], "printer_ids": [3, 4]},
        headers=auth_headers,
    ).json()
    assert body["events"] == ["printer_offline"]
    assert body["printer_ids"] == [3, 4]


def test_invalid_events_are_dropped(client: TestClient, auth_headers):
    body = _create(
        client, auth_headers, events=["print_completed", "bogus", "print_completed"]
    ).json()
    assert body["events"] == ["print_completed"]  # invalid + dupes removed


def test_delete_channel(client: TestClient, auth_headers):
    cid = _create(client, auth_headers).json()["id"]
    assert (
        client.delete(
            f"/api/v1/notifications/channels/{cid}", headers=auth_headers
        ).status_code
        == 204
    )
    assert client.get("/api/v1/notifications/channels", headers=auth_headers).json() == []


def test_test_send_reports_render_error(client: TestClient, auth_headers):
    # Telegram channel missing chat_id -> render error, surfaced as ok=False.
    cid = _create(
        client,
        auth_headers,
        target="telegram",
        config={"bot_token": "t"},
        events=["print_completed"],
    ).json()["id"]
    out = client.post(
        f"/api/v1/notifications/channels/{cid}/test", headers=auth_headers
    ).json()
    assert out["ok"] is False
    assert "chat_id" in out["error"]


def test_deliveries_endpoint_empty(client: TestClient, auth_headers):
    assert client.get("/api/v1/notifications/deliveries", headers=auth_headers).json() == []
