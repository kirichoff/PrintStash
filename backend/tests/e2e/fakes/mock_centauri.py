"""In-process fake for ``ElegooCentauriClient``'s ``_CentauriConnection`` seam.

Elegoo speaks a proprietary SDCP websocket protocol that ``pycentauri``
already implements against real hardware; there is no documented way to
point it at a plain test socket without TLS the way PrusaLink/OctoPrint's
plain-HTTP transports allow (see ``# ponytail`` note below). Instead this
fakes the *seam* ``ElegooCentauriClient`` already exposes for testing
(``connector: Callable[[bool], Awaitable[_CentauriConnection]]``), backed by
the same wall-clock ``PrintSim`` the HTTP-based emulators use, and returning
real ``pycentauri.models.Status``/``PrintInfo`` objects so
``ElegooCentauriClient.normalize_status`` runs unmodified.

# ponytail: seam-level fake, not a real SDCP-over-websocket server — pycentauri
# offers no test hook to redirect its TLS/handshake to a bare loopback socket.
# Upgrade path: a real SDCP-WS emulator, if/when pycentauri exposes one.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Callable

from pycentauri.models import PrintStatus, Status

from app.services.elegoo_centauri import ElegooCentauriError

from .print_sim import PrintSim

# PrintSim.state -> SDCP PrintInfo.Status code (see pycentauri.models.PrintStatus).
_STATE_CODES = {
    "standby": int(PrintStatus.IDLE),
    "printing": int(PrintStatus.PRINTING),
    "paused": int(PrintStatus.PAUSED),
    "complete": int(PrintStatus.COMPLETED),
    "cancelled": int(PrintStatus.STOPPED),
    "error": int(PrintStatus.ERROR),
}

# How often watch() pushes a status tick.
PUSH_INTERVAL_S = 0.2


class FakeCentauriConnection:
    """Scriptable ``_CentauriConnection`` driven by a ``PrintSim``."""

    def __init__(self, sim: PrintSim) -> None:
        self.sim = sim
        self.closed = False
        self.calls: list[tuple[str, Any]] = []

    def _status(self) -> Status:
        self.sim.progress()  # latch printing -> complete
        active = self.sim.is_active()
        return Status.from_payload(
            {
                "TempOfNozzle": 210.0 if active else 25.0,
                "TempTargetNozzle": 210.0 if active else 0.0,
                "TempOfHotbed": 60.0 if active else 25.0,
                "TempTargetHotbed": 60.0 if active else 0.0,
                "TempOfBox": 32.0 if active else 22.0,
                "PrintInfo": {
                    "Status": _STATE_CODES.get(self.sim.state, int(PrintStatus.ERROR)),
                    "Filename": self.sim.filename,
                    "Progress": round(self.sim.progress() * 100),
                    "CurrentTicks": self.sim.elapsed(),
                },
                "Message": self.sim.message,
            }
        )

    async def status(self) -> Status:
        return self._status()

    async def watch(self) -> AsyncIterator[Status]:
        while True:
            yield self._status()
            await asyncio.sleep(PUSH_INTERVAL_S)

    async def start_print(self, filename: str, **kwargs: Any) -> Any:
        self.calls.append(("start_print", (filename, kwargs)))
        self.sim.start(filename)
        return {}

    async def pause(self) -> Any:
        self.calls.append(("pause", None))
        self.sim.pause()
        return {}

    async def resume(self) -> Any:
        self.calls.append(("resume", None))
        self.sim.resume()
        return {}

    async def stop(self) -> Any:
        self.calls.append(("stop", None))
        self.sim.cancel()
        return {}

    async def close(self) -> None:
        self.closed = True


def make_connector(
    sim: PrintSim,
    *,
    expected_access_code: str | None = None,
    given_access_code: str | None = None,
    fail_transport: bool = False,
) -> tuple[Callable[[bool], Any], FakeCentauriConnection]:
    """Build a ``Connector`` closure plus the connection it will hand back.

    Pass ``expected_access_code``/``given_access_code`` to simulate a Carbon 2
    access-code check (real firmware rejects the handshake with an
    "access code" error); ``fail_transport`` simulates a network-layer drop.
    """
    connection = FakeCentauriConnection(sim)

    async def connector(enable_control: bool) -> FakeCentauriConnection:
        # Mirrors ElegooCentauriClient._connect's own contract: the connector
        # is responsible for translating transport/auth failures into
        # ElegooCentauriError itself — `_with_connection`'s try/except only
        # wraps `action(connection)`, not the connect call.
        if fail_transport:
            raise ElegooCentauriError("simulated connection refused")
        if expected_access_code is not None and given_access_code != expected_access_code:
            raise ElegooCentauriError(
                "access code rejected by printer", code="provider_authentication_failed"
            )
        return connection

    return connector, connection
