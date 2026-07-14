from __future__ import annotations

import asyncio

import httpx

from app.services.release_check import (
    GITHUB_LATEST_RELEASE_URL,
    _fetch_release_status,
    is_newer_release,
)


def test_release_versions_compare_semantically() -> None:
    assert is_newer_release("0.10.1", "0.10.0") is True
    assert is_newer_release("v1.0.0", "0.10.9") is True
    assert is_newer_release("0.9.9", "0.10.0") is False
    assert is_newer_release("not-a-version", "0.10.0") is False


def test_fetch_release_status_reports_available_update() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == GITHUB_LATEST_RELEASE_URL
        return httpx.Response(
            200,
            json={
                "tag_name": "v0.10.1",
                "html_url": "https://github.com/xiao-villamor/PrintStash/releases/tag/v0.10.1",
                "published_at": "2026-07-14T10:00:00Z",
            },
        )

    result = asyncio.run(
        _fetch_release_status("0.10.0", transport=httpx.MockTransport(handler))
    )

    assert result["status"] == "update_available"
    assert result["current_version"] == "0.10.0"
    assert result["latest_version"] == "0.10.1"
    assert result["update_available"] is True


def test_fetch_release_status_degrades_when_github_is_unavailable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    result = asyncio.run(
        _fetch_release_status("0.10.0", transport=httpx.MockTransport(handler))
    )

    assert result["status"] == "unavailable"
    assert result["update_available"] is False
    assert result["latest_version"] is None
