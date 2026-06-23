"""Shared SSRF guard: reject URLs that resolve to non-public addresses.

Used anywhere the server makes an outbound request to a user-supplied URL
(URL/zip imports, notification webhooks). Centralised so the security-critical
IP predicate has a single source of truth.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


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


def is_public_url(url: str) -> bool:
    """True if ``url`` is HTTP(S) and every resolved address is public.

    Non-raising variant for callers that want a boolean gate. Returns ``False``
    for non-HTTP schemes, a missing host, DNS failure, or any address that
    resolves to a non-public range (defends against SSRF + DNS-rebind to a
    private host).
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, parts.port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    addrs = {info[4][0] for info in infos}
    if not addrs:
        return False
    return all(is_public_ip(addr) for addr in addrs)
