from __future__ import annotations

import time

from app.core.ratelimit import RateLimiter


def test_allows_up_to_limit():
    limiter = RateLimiter(limit=3, window_s=60.0)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True


def test_blocks_after_limit():
    limiter = RateLimiter(limit=2, window_s=60.0)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False


def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window_s=60.0)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("5.6.7.8") is True
    assert limiter.check("1.2.3.4") is False
    assert limiter.check("5.6.7.8") is False


def test_window_expires_old_hits():
    limiter = RateLimiter(limit=1, window_s=0.05)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False
    time.sleep(0.06)
    assert limiter.check("1.2.3.4") is True


def test_reset_clears_all_keys():
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.check("1.2.3.4")
    assert limiter.check("1.2.3.4") is False
    limiter.reset()
    assert limiter.check("1.2.3.4") is True
