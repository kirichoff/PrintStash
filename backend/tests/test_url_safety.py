"""Unit coverage for the shared SSRF guard (``app.core.url_safety``)."""

from __future__ import annotations

import pytest

from app.core.url_safety import is_public_ip, is_public_url


@pytest.mark.parametrize(
    "ip,expected",
    [
        ("8.8.8.8", True),
        ("1.1.1.1", True),
        ("127.0.0.1", False),  # loopback
        ("10.0.0.1", False),  # private
        ("192.168.1.5", False),  # private
        ("169.254.169.254", False),  # link-local (cloud metadata)
        ("::1", False),  # ipv6 loopback
        ("not-an-ip", False),
    ],
)
def test_is_public_ip(ip, expected):
    assert is_public_ip(ip) is expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("ftp://example.com/x", False),  # non-http scheme
        ("http:///nohost", False),  # missing host
        ("http://127.0.0.1/hook", False),  # literal loopback — no DNS needed
        ("http://169.254.169.254/latest/meta-data", False),  # metadata endpoint
        ("https://10.1.2.3/hook", False),  # literal private
    ],
)
def test_is_public_url_blocks(url, expected):
    # Literal-IP and scheme/host cases resolve without touching real DNS.
    assert is_public_url(url) is expected
