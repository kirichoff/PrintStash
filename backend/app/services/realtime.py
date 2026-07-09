"""Non-blocking pub/sub seam for WebSocket fan-out.

``InProcessBus`` is the only adapter today — Stage 4/cloud can swap in a
Redis-backed bus at the construction site with no change to callers, since
they only depend on the ``RealtimeBus`` protocol.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Protocol, Set

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)

_SEND_TIMEOUT_S = 2.0


class RealtimeBus(Protocol):
    async def publish(self, channel: str, payload: Dict[str, Any]) -> None: ...

    async def subscribe(self, channel: str, ws: WebSocket) -> None: ...

    async def unsubscribe(self, channel: str, ws: WebSocket) -> None: ...


class InProcessBus:
    """Single-process fan-out. Subscriber sends run concurrently so one slow
    or dead socket can't delay delivery to the rest of a channel."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            self._subscribers.setdefault(channel, set()).add(ws)

    async def unsubscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            subs = self._subscribers.get(channel)
            if subs and ws in subs:
                subs.remove(ws)

    async def publish(self, channel: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subscribers.get(channel, ()))
        if not subs:
            return

        async def _send(ws: WebSocket) -> WebSocket | None:
            try:
                async with asyncio.timeout(_SEND_TIMEOUT_S):
                    await ws.send_json(payload)
                return None
            except Exception:
                return ws

        results = await asyncio.gather(*(_send(ws) for ws in subs))
        dead = [r for r in results if r is not None]
        if dead:
            async with self._lock:
                for ws in dead:
                    self._subscribers.get(channel, set()).discard(ws)
