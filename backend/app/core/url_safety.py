"""Shared SSRF guard: reject URLs that resolve to non-public addresses.

Used anywhere the server makes an outbound request to a user-supplied URL
(URL/zip imports, notification webhooks). Centralised so the security-critical
IP predicate has a single source of truth.

Validating a hostname and then handing the *hostname* to an HTTP client leaves a
DNS-rebinding window: the client resolves again, and the attacker's second
answer can be 127.0.0.1. Callers therefore resolve once via
:func:`resolve_public_target` and fetch through :func:`pinned_transport`, which
dials the address that was actually validated. The URL keeps its hostname, so
TLS SNI and certificate verification stay honest.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlsplit

import httpx
from httpcore import AnyIOBackend, AsyncNetworkStream


class UnsafeUrlError(Exception):
    """The URL is not safe to fetch server-side. ``reason`` is a stable code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def is_public_ip(ip_str: str) -> bool:
    """True if ``ip_str`` is a routable public address (not private/loopback/etc.)."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


@dataclass(frozen=True)
class PinnedTarget:
    """A URL whose every resolved address was public, plus the one we will dial."""

    url: str
    host: str
    port: int
    ip: str


def resolve_public_target(url: str) -> PinnedTarget:
    """Resolve *url* once and require every answer to be a public address.

    Raises :class:`UnsafeUrlError`. Every returned address is checked, not only
    the one we dial: a host answering with both a public and a private address
    is an attack, not a fallback.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrlError("url_scheme_not_allowed")
    host = parts.hostname
    if not host:
        raise UnsafeUrlError("url_host_missing")
    port = parts.port or (443 if parts.scheme == "https" else 80)

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError("url_dns_resolution_failed") from exc

    addrs = [info[4][0] for info in infos]
    if not addrs:
        raise UnsafeUrlError("url_dns_resolution_failed")
    for addr in addrs:
        if not is_public_ip(addr):
            raise UnsafeUrlError("url_target_not_public")

    return PinnedTarget(url=url, host=host, port=port, ip=addrs[0])


def is_public_url(url: str) -> bool:
    """Boolean gate for callers that only need to reject, not to fetch."""
    try:
        resolve_public_target(url)
    except UnsafeUrlError:
        return False
    return True


class _PinnedBackend(AnyIOBackend):
    """Network backend that dials *ip* whatever hostname it is handed.

    Only the TCP peer is substituted. The request URL still carries the real
    hostname, so Host, SNI and certificate hostname verification are unchanged.
    Rewriting the URL to the bare IP instead would quietly drop the certificate
    hostname check.
    """

    def __init__(self, ip: str) -> None:
        self._ip = ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[object] | None = None,
    ) -> AsyncNetworkStream:
        return await super().connect_tcp(
            self._ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,  # type: ignore[arg-type]
        )


def pinned_transport(target: PinnedTarget) -> httpx.AsyncHTTPTransport:
    """An httpx transport that connects only to *target*'s validated address.

    ponytail: reaches into ``transport._pool`` because httpx exposes no public
    hook for the network backend. Pinned by a test that asserts the dialled peer.
    """
    transport = httpx.AsyncHTTPTransport(retries=0)
    transport._pool._network_backend = _PinnedBackend(target.ip)  # type: ignore[attr-defined]
    return transport
