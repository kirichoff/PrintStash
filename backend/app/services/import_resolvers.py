"""Resolve model *page* URLs to direct download URLs.

Users paste the page they are looking at — e.g.
``https://www.printables.com/model/3161-3d-benchy/files`` — rather than a
direct download link. Each host keeps the real file behind an API call keyed by
the model id embedded in the page URL. The resolvers here turn a recognised
page URL into a direct download URL that :func:`importer.download_to_staging`
can fetch; that function re-runs the SSRF guard on every hop, including the
resolved one, so resolution never bypasses the public-IP check.

Contract of :func:`resolve_page_url`:

* **Unrecognised host** (or a known host whose URL carries no model id) →
  ``None``. The caller treats the original URL as an already-direct download.
* **Recognised page that resolves** → a direct download URL string.
* **Recognised page that fails to resolve** → ``ImportError_`` with a
  host-specific code (e.g. ``printables_resolve_failed``) so the UI can tell the
  user to paste a direct link instead of silently downloading the HTML page.

The host APIs dictate the request/response shapes (that is their public
contract); everything else here — dispatch, pack selection, JSON walking,
graceful degradation — is ours.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urlsplit

from app.core.http_client import get_http_client
from app.core.logging import get_logger
from app.services.importer import ImportError_

logger = get_logger(__name__)

# A browser-like UA: model hosts gate their APIs/HTML behind one.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)
_TIMEOUT = 30.0

# Suffixes that mark a URL as pointing at a downloadable model/bundle.
_MODEL_EXTS = (
    ".zip",
    ".3mf",
    ".stl",
    ".obj",
    ".step",
    ".stp",
    ".gcode",
    ".g",
    ".gco",
)

_PRINTABLES_HOSTS = {"printables.com", "www.printables.com"}
_THINGIVERSE_HOSTS = {"thingiverse.com", "www.thingiverse.com"}
_PRINTABLES_GRAPHQL = "https://api.printables.com/graphql/"


# --------------------------------------------------------------------------- #
# Host classification + id extraction
# --------------------------------------------------------------------------- #
def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _printables_id(url: str) -> Optional[str]:
    m = re.search(r"/model/(\d+)", urlsplit(url).path)
    return m.group(1) if m else None


def _makerworld_id(url: str) -> Optional[str]:
    m = re.search(r"/models/(\d+)", urlsplit(url).path)
    return m.group(1) if m else None


def _thingiverse_id(url: str) -> Optional[str]:
    path = urlsplit(url).path
    m = re.search(r"thing:(\d+)", path) or re.search(r"/things/(\d+)", path)
    return m.group(1) if m else None


def classify_page(url: str) -> Optional[str]:
    """Return the resolver name for a known model *page*, else ``None``.

    A host is only "known" when we can also pull a model id from the path, so a
    direct ``files.printables.com`` blob URL (different host, no ``/model/<id>``)
    is correctly treated as a direct download rather than a page.
    """
    host = _host(url)
    if host in _PRINTABLES_HOSTS and _printables_id(url):
        return "printables"
    if (host == "makerworld.com" or host.endswith(".makerworld.com")) and _makerworld_id(url):
        return "makerworld"
    if host in _THINGIVERSE_HOSTS and _thingiverse_id(url):
        return "thingiverse"
    return None


# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #
def _looks_like_download(url: str) -> bool:
    lower = url.split("?", 1)[0].lower()
    return lower.endswith(_MODEL_EXTS) or "/download" in url.lower()


def _first_download_url(data: Any) -> Optional[str]:
    """Walk a JSON structure breadth-first for the first plausible file URL.

    Direct ``url``/``downloadUrl`` keys win; otherwise any string value that
    looks like a model download. Returns ``None`` if nothing qualifies.
    """
    stack: list[Any] = [data]
    fallback: Optional[str] = None
    while stack:
        current = stack.pop(0)
        if isinstance(current, dict):
            for key in ("url", "downloadUrl", "download_url", "link"):
                value = current.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
        elif isinstance(current, str):
            if (
                fallback is None
                and current.startswith(("http://", "https://"))
                and _looks_like_download(current)
            ):
                fallback = current
    return fallback


def _extract_next_data(html: str) -> Optional[Any]:
    """Pull the Next.js ``__NEXT_DATA__`` JSON blob out of a page's HTML."""
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- #
# Printables (GraphQL)
# --------------------------------------------------------------------------- #
_PRINTABLES_META_QUERY = """
query ($id: ID!) {
  print(id: $id) {
    id
    downloadPacks { id fileType }
    stls { id name }
  }
}
"""

_PRINTABLES_LINK_MUTATION = """
mutation ($printId: ID!, $source: DownloadSourceEnum!, $fileType: DownloadFileTypeEnum, $id: ID, $files: [DownloadFileInput!]) {
  getDownloadLink(printId: $printId, source: $source, fileType: $fileType, id: $id, files: $files) {
    ok
    output { link files { link } }
  }
}
"""


async def _printables_graphql(query: str, variables: dict, referer: str) -> Any:
    client = get_http_client()
    resp = await client.post(
        _PRINTABLES_GRAPHQL,
        json={"query": query, "variables": variables},
        headers={
            "User-Agent": _BROWSER_UA,
            "Accept": "application/json",
            "Origin": "https://www.printables.com",
            "Referer": referer,
        },
        timeout=_TIMEOUT,
    )
    if resp.status_code in (401, 403, 429):
        raise ImportError_("printables_blocked")
    resp.raise_for_status()
    return resp.json()


def _pick_printables_pack(packs: Any) -> Optional[str]:
    """Prefer the all-model-files pack; fall back to any pack with an id."""
    if not isinstance(packs, list):
        return None
    for pack in packs:
        if isinstance(pack, dict) and pack.get("fileType") == "MODEL_FILES" and pack.get("id"):
            return str(pack["id"])
    for pack in packs:
        if isinstance(pack, dict) and pack.get("id"):
            return str(pack["id"])
    return None


def _printables_link_from_output(payload: Any) -> Optional[str]:
    result = (payload or {}).get("data", {}).get("getDownloadLink") or {}
    output = result.get("output") or {}
    if isinstance(output.get("link"), str):
        return output["link"]
    for entry in output.get("files") or []:
        if isinstance(entry, dict) and isinstance(entry.get("link"), str):
            return entry["link"]
    return None


async def _resolve_printables(url: str) -> Optional[str]:
    print_id = _printables_id(url)
    if not print_id:
        return None
    meta = await _printables_graphql(_PRINTABLES_META_QUERY, {"id": print_id}, url)
    print_obj = (meta or {}).get("data", {}).get("print")
    if not isinstance(print_obj, dict):
        return None

    pack_id = _pick_printables_pack(print_obj.get("downloadPacks"))
    if pack_id:
        payload = await _printables_graphql(
            _PRINTABLES_LINK_MUTATION,
            {"printId": print_id, "source": "model_detail", "fileType": "pack", "id": pack_id},
            url,
        )
        link = _printables_link_from_output(payload)
        if link:
            return link

    stl_ids = [
        str(s["id"])
        for s in (print_obj.get("stls") or [])
        if isinstance(s, dict) and s.get("id")
    ]
    if stl_ids:
        payload = await _printables_graphql(
            _PRINTABLES_LINK_MUTATION,
            {
                "printId": print_id,
                "source": "model_detail",
                "files": [{"fileType": "stl", "ids": stl_ids}],
            },
            url,
        )
        link = _printables_link_from_output(payload)
        if link:
            return link
    return None


# --------------------------------------------------------------------------- #
# MakerWorld (Next.js page → instance/model download API)
# --------------------------------------------------------------------------- #
def _makerworld_api_headers(referer: str, nonce: Optional[str], cookie: Optional[str]) -> dict:
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "application/json",
        "X-BBL-Client-Type": "web",
        "X-BBL-Client-Name": "MakerWorld",
        "Referer": referer,
    }
    if nonce:
        headers["X-Nonce"] = nonce
    if cookie:
        headers["Cookie"] = cookie
    return headers


async def _makerworld_fetch_page(url: str, cookie: Optional[str]) -> Optional[str]:
    client = get_http_client()
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if cookie:
        headers["Cookie"] = cookie
    resp = await client.get(url, headers=headers, follow_redirects=True, timeout=_TIMEOUT)
    if resp.status_code != 200:
        return None
    return resp.text


async def _makerworld_api_get(
    api_url: str, referer: str, nonce: Optional[str], cookie: Optional[str]
) -> Optional[Any]:
    client = get_http_client()
    resp = await client.get(
        api_url,
        headers=_makerworld_api_headers(referer, nonce, cookie),
        follow_redirects=True,
        timeout=_TIMEOUT,
    )
    if resp.status_code in (401, 403, 429):
        raise ImportError_("makerworld_blocked")
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def _makerworld_page_facts(next_data: Any) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return ``(design_id, instance_id, nonce)`` pulled from ``__NEXT_DATA__``."""
    try:
        props = next_data["props"]["pageProps"]
    except (KeyError, TypeError):
        return None, None, None
    design = props.get("design") or {}
    design_id = str(design["id"]) if isinstance(design, dict) and design.get("id") else None
    instance_id = None
    if isinstance(design, dict):
        if design.get("defaultInstanceId"):
            instance_id = str(design["defaultInstanceId"])
        else:
            for inst in design.get("instances") or []:
                if isinstance(inst, dict) and inst.get("id"):
                    instance_id = str(inst["id"])
                    break
    nonce = props.get("x-nonce")
    nonce = nonce if isinstance(nonce, str) and nonce.strip() else None
    return design_id, instance_id, nonce


async def _resolve_makerworld(url: str, cookie: Optional[str]) -> Optional[str]:
    model_id = _makerworld_id(url)
    design_id = instance_id = nonce = None

    html = await _makerworld_fetch_page(url, cookie)
    if html:
        next_data = _extract_next_data(html)
        if next_data is not None:
            # A page sometimes already embeds a usable link in its hydration JSON.
            link = _first_download_url(next_data)
            if link:
                return link
            design_id, instance_id, nonce = _makerworld_page_facts(next_data)

    if instance_id:
        api = (
            f"https://makerworld.com/api/v1/design-service/instance/"
            f"{instance_id}/f3mf?type=download&fileType=3mfstl"
        )
        data = await _makerworld_api_get(api, url, nonce, cookie)
        link = _first_download_url(data) if data is not None else None
        if link:
            return link

    target = design_id or model_id
    if target:
        api = f"https://makerworld.com/api/v1/models/{target}/download"
        data = await _makerworld_api_get(api, url, nonce, cookie)
        link = _first_download_url(data) if data is not None else None
        if link:
            return link
    return None


# --------------------------------------------------------------------------- #
# Thingiverse (stable public per-thing zip endpoint)
# --------------------------------------------------------------------------- #
async def _resolve_thingiverse(url: str, cookie: Optional[str]) -> Optional[str]:
    thing_id = _thingiverse_id(url)
    if not thing_id:
        return None
    # Public things expose every file as one zip at this stable URL; it
    # 302-redirects to a CDN blob that ``download_to_staging`` follows. No API
    # token needed for public models, so we prefer it over the token dance.
    return f"https://www.thingiverse.com/thing:{thing_id}/zip"


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
async def resolve_page_url(
    url: str,
    *,
    makerworld_cookie: Optional[str] = None,
    thingiverse_cookie: Optional[str] = None,
) -> Optional[str]:
    """Resolve a known model *page* URL to a direct download URL (see module doc)."""
    kind = classify_page(url)
    if kind is None:
        return None

    try:
        if kind == "printables":
            resolved = await _resolve_printables(url)
        elif kind == "makerworld":
            resolved = await _resolve_makerworld(url, makerworld_cookie)
        else:
            resolved = await _resolve_thingiverse(url, thingiverse_cookie)
    except ImportError_:
        raise
    except Exception as exc:  # noqa: BLE001 — network/parse boundary
        logger.warning("page resolution errored for %s: %s", url, exc)
        raise ImportError_(f"{kind}_resolve_failed") from exc

    if not resolved:
        raise ImportError_(f"{kind}_resolve_failed")
    return resolved
