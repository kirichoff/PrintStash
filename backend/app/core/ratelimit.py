"""In-process per-IP sliding-window rate limiting for FastAPI routes.

ponytail: process-local dict, correct for a single worker only. A
multi-worker or multi-process deployment needs a shared store (Redis/Upstash)
since each worker would otherwise track its own independent window.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int, window_s: float) -> None:
        self._limit = limit
        self._window = window_s
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits[key] if now - t < self._window]
            if len(hits) >= self._limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def rate_limit(limit: int, window_s: float) -> Callable[[Request], None]:
    """Build a FastAPI dependency enforcing *limit* requests per *window_s* per IP."""
    limiter = RateLimiter(limit=limit, window_s=window_s)

    def _dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.check(client):
            raise HTTPException(status_code=429, detail="rate_limited")

    _dependency.limiter = limiter  # type: ignore[attr-defined]
    return _dependency
