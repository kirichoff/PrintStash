"""Unit coverage for ``import_resolvers`` — turning model *page* URLs into
direct download URLs.

The host HTTP calls (Printables GraphQL, MakerWorld page + API) are patched at
the module's small network helpers, so these tests exercise the dispatch, id
extraction, pack selection and JSON-walking logic without any real network.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.services import import_resolvers as r
from app.services.importer import ImportError_


# --------------------------------------------------------------------------- #
# Host classification + id extraction (pure functions)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.printables.com/model/3161-3d-benchy", "printables"),
        ("https://www.printables.com/model/3161-3d-benchy/files", "printables"),
        ("https://printables.com/model/3161", "printables"),
        ("https://makerworld.com/en/models/1123776-original-3d-benchy", "makerworld"),
        ("https://makerworld.com/es/models/1123776?from=search#x", "makerworld"),
        ("https://www.thingiverse.com/thing:763622", "thingiverse"),
        ("https://www.thingiverse.com/thing:763622/files", "thingiverse"),
        # Direct blob URLs are not pages — different host / no model id.
        ("https://files.printables.com/abc/3dbenchy.stl", None),
        ("https://example.com/model.zip", None),
        # Known host but no extractable id -> treated as direct, not a page.
        ("https://www.printables.com/social/123-user", None),
    ],
)
def test_classify_page(url: str, expected) -> None:
    assert r.classify_page(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        # Regression: endswith("makerworld.com") used to classify look-alike
        # hosts as MakerWorld pages.
        "https://evilmakerworld.com/en/models/123",
        "https://makerworld.com.attacker.test/models/123",
        "https://notmakerworld.com/models/123",
    ],
)
def test_classify_page_rejects_lookalike_makerworld_hosts(url: str) -> None:
    assert r.classify_page(url) is None


def test_classify_page_accepts_makerworld_subdomain() -> None:
    assert r.classify_page("https://www.makerworld.com/en/models/123") == "makerworld"


def test_classify_page_is_case_insensitive_on_host() -> None:
    assert r.classify_page("https://WWW.PRINTABLES.COM/model/3161") == "printables"


def test_classify_page_handles_garbage_input() -> None:
    assert r.classify_page("not a url") is None
    assert r.classify_page("") is None


def test_id_extractors() -> None:
    assert r._printables_id("https://www.printables.com/model/3161-3d-benchy/files") == "3161"
    assert r._makerworld_id("https://makerworld.com/en/models/1123776-x") == "1123776"
    assert r._thingiverse_id("https://www.thingiverse.com/thing:763622") == "763622"
    assert r._thingiverse_id("https://www.thingiverse.com/things/763622/files") == "763622"


# --------------------------------------------------------------------------- #
# Generic JSON helpers
# --------------------------------------------------------------------------- #
def test_first_download_url_prefers_keyed_link() -> None:
    data = {"a": {"nested": {"downloadUrl": "https://cdn.test/x.zip"}}, "b": [1, 2]}
    assert r._first_download_url(data) == "https://cdn.test/x.zip"


def test_first_download_url_falls_back_to_model_like_string() -> None:
    data = {"meta": "hello", "links": ["https://cdn.test/model.3mf", "not-a-url"]}
    assert r._first_download_url(data) == "https://cdn.test/model.3mf"


def test_first_download_url_none_when_nothing_matches() -> None:
    assert r._first_download_url({"meta": "hello", "n": 3, "page": "https://x.test/about"}) is None


def test_pick_printables_pack_prefers_model_files() -> None:
    packs = [{"id": 5, "fileType": "OTHER"}, {"id": 9, "fileType": "MODEL_FILES"}]
    assert r._pick_printables_pack(packs) == "9"
    # Falls back to the first pack with an id when there's no MODEL_FILES pack.
    assert r._pick_printables_pack([{"id": 7, "fileType": "GCODE"}]) == "7"
    assert r._pick_printables_pack([]) is None


def test_first_download_url_keyed_link_beats_deep_fallback() -> None:
    # A keyed url anywhere wins over a model-looking bare string.
    data = {"files": ["https://cdn.test/a.stl"], "meta": {"url": "https://cdn.test/real.zip"}}
    assert r._first_download_url(data) == "https://cdn.test/real.zip"


def test_first_download_url_ignores_non_http_keyed_values() -> None:
    # A relative or non-http "url" must not be returned as a download link.
    data = {"url": "/local/path.zip", "links": ["https://cdn.test/model.stl"]}
    assert r._first_download_url(data) == "https://cdn.test/model.stl"


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://cdn.test/model.stl", True),
        ("https://cdn.test/model.3MF", True),  # case-insensitive ext
        ("https://cdn.test/get?file=model.stl", False),  # ext only in query
        ("https://cdn.test/api/download/123", True),  # /download path
        ("https://cdn.test/image.png", False),
        ("https://cdn.test/about", False),
    ],
)
def test_looks_like_download(url: str, expected: bool) -> None:
    assert r._looks_like_download(url) is expected


def test_extract_next_data_round_trips() -> None:
    html = '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"x":1}}</script></html>'
    assert r._extract_next_data(html) == {"props": {"x": 1}}
    assert r._extract_next_data("<html>no next data</html>") is None


# --------------------------------------------------------------------------- #
# resolve_page_url dispatch
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_resolve_unknown_host_returns_none() -> None:
    # No network: unknown hosts short-circuit before any resolver runs.
    assert await r.resolve_page_url("https://example.com/foo.zip") is None


@pytest.mark.asyncio
async def test_resolve_thingiverse_builds_zip_url() -> None:
    url = "https://www.thingiverse.com/thing:763622/files"
    assert await r.resolve_page_url(url) == "https://www.thingiverse.com/thing:763622/zip"


@pytest.mark.asyncio
async def test_resolve_printables_uses_pack_link() -> None:
    meta = {"data": {"print": {"id": "3161", "downloadPacks": [{"id": "42", "fileType": "MODEL_FILES"}], "stls": []}}}
    link_payload = {"data": {"getDownloadLink": {"ok": True, "output": {"link": "https://files.printables.test/pack.zip"}}}}

    graphql = AsyncMock(side_effect=[meta, link_payload])
    with patch.object(r, "_printables_graphql", graphql):
        out = await r.resolve_page_url("https://www.printables.com/model/3161-3d-benchy")

    assert out == "https://files.printables.test/pack.zip"
    assert graphql.await_count == 2  # meta query, then link mutation


@pytest.mark.asyncio
async def test_resolve_printables_unresolved_raises_host_error() -> None:
    meta = {"data": {"print": {"id": "3161", "downloadPacks": [], "stls": []}}}
    with patch.object(r, "_printables_graphql", AsyncMock(return_value=meta)):
        with pytest.raises(ImportError_) as exc:
            await r.resolve_page_url("https://www.printables.com/model/3161-3d-benchy")
    assert str(exc.value) == "printables_resolve_failed"


@pytest.mark.asyncio
async def test_resolve_printables_network_error_becomes_host_error() -> None:
    with patch.object(r, "_printables_graphql", AsyncMock(side_effect=RuntimeError("boom"))):
        with pytest.raises(ImportError_) as exc:
            await r.resolve_page_url("https://www.printables.com/model/3161-3d-benchy")
    assert str(exc.value) == "printables_resolve_failed"


@pytest.mark.asyncio
async def test_resolve_makerworld_uses_link_from_next_data() -> None:
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"design":{"id":1,"downloadUrl":"https://cdn.makerworld.test/x.3mf"}}}}'
        "</script>"
    )
    with patch.object(r, "_makerworld_fetch_page", AsyncMock(return_value=html)):
        out = await r.resolve_page_url("https://makerworld.com/en/models/1123776-x")
    assert out == "https://cdn.makerworld.test/x.3mf"


@pytest.mark.asyncio
async def test_resolve_makerworld_falls_back_to_model_api() -> None:
    # Page HTML has no embedded link and no instance id -> hit the model API.
    html = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>'
    api_data = {"url": "https://cdn.makerworld.test/bundle.zip"}
    with (
        patch.object(r, "_makerworld_fetch_page", AsyncMock(return_value=html)),
        patch.object(r, "_makerworld_api_get", AsyncMock(return_value=api_data)),
    ):
        out = await r.resolve_page_url("https://makerworld.com/en/models/1123776-x")
    assert out == "https://cdn.makerworld.test/bundle.zip"
