"""Thread-safe in-process recorder for fake external services.

The fake provider/Moonraker servers run in a uvicorn thread with their own event
loop while the test drives the app from the main thread. Both sides touch this
recorder, so access is guarded by a lock. Tests read the captured requests
directly (same process) rather than over HTTP — the fakes are a real socket on
the *egress* path, which is the whole point, but introspection stays in-process.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Received:
    """One inbound request captured at a fake external endpoint."""

    target: str  # "discord" | "telegram" | "ntfy" | "webhook" | ...
    method: str
    path: str
    headers: Dict[str, str]
    json: Optional[Any] = None
    body: Optional[bytes] = None
    status_returned: int = 200


class Recorder:
    """Append-only log of received requests, queryable by target."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: List[Received] = []
        # Per-key call counters, used by the flaky endpoint.
        self._counters: Dict[str, int] = field(default_factory=dict)  # type: ignore[assignment]
        self._counters = {}

    def record(self, item: Received) -> None:
        with self._lock:
            self._items.append(item)

    def for_target(self, target: str) -> List[Received]:
        with self._lock:
            return [i for i in self._items if i.target == target]

    def all(self) -> List[Received]:
        with self._lock:
            return list(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._counters.clear()

    def bump(self, key: str) -> int:
        """Increment and return the call count for ``key`` (1 on first call)."""
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1
            return self._counters[key]
