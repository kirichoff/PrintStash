"""Integration pack for the Bambu LAN provider against its three fakes.

``BambuLanProvider`` is not one transport: status polling is real HTTPS
(exercised end to end here against a self-signed loopback server), commands
go over MQTT and uploads over implicit FTPS — neither has a constructor
seam, so those two are patched at the instance level (see
``mock_bambu.py`` docstring).
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.printer_provider import BambuLanProvider, ProviderError
from tests.e2e.fakes.mock_bambu import (
    FakeFtpTls,
    make_mqtt_factory,
    start_status_server,
)
from tests.e2e.fakes.print_sim import PrintSim

REMOTE = "demo.gcode"
ACCESS_CODE = "12345678"


def _provider(
    sim: PrintSim, *, printer_access_code: str = ACCESS_CODE, expected_access_code: str | None = ACCESS_CODE
) -> tuple[BambuLanProvider, list]:
    provider = BambuLanProvider(
        host="127.0.0.1", serial="01S00A000000000", access_code=printer_access_code
    )
    factory, built = make_mqtt_factory(
        sim, attempted_access_code=printer_access_code, expected_access_code=expected_access_code
    )
    provider._mqtt_client = factory  # instance override; see mock_bambu.py docstring
    return provider, built


async def _wait_state(provider: BambuLanProvider, state: str, *, timeout: float = 10.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        result = await provider.query_status()
        if result["result"]["status"]["print_stats"]["state"] == state:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"never reached state {state!r}")


def test_send_print_completes() -> None:
    sim = PrintSim(total_mm=1000.0, total_seconds=10.0, print_seconds=1.0)
    running = start_status_server(sim)
    try:
        provider, built = _provider(sim)

        async def _run() -> None:
            await provider.start(REMOTE)
            assert built[0].published[0]["print"]["command"] == "gcode_file"
            await _wait_state(provider, "complete")

        asyncio.run(_run())
    finally:
        running.stop()


def test_pause_then_resume_runs_to_completion() -> None:
    sim = PrintSim(total_mm=1000.0, total_seconds=10.0, print_seconds=1.5)
    running = start_status_server(sim)
    try:
        provider, _built = _provider(sim)

        async def _run() -> None:
            await provider.start(REMOTE)
            await provider.pause()
            await _wait_state(provider, "paused")
            await provider.resume()
            await _wait_state(provider, "complete")

        asyncio.run(_run())
    finally:
        running.stop()


def test_cancel_reports_finish() -> None:
    # Bambu's gcode_state has no distinct "cancelled" value — a stopped print
    # reports FINISH, same as a completed one (see _SIM_TO_BAMBU_STATE).
    sim = PrintSim(total_mm=1000.0, total_seconds=10.0, print_seconds=5.0)
    running = start_status_server(sim)
    try:
        provider, built = _provider(sim)

        async def _run() -> None:
            await provider.start(REMOTE)
            await _wait_state(provider, "printing")
            await provider.cancel()
            await _wait_state(provider, "complete")
            assert built[-1].published[-1]["print"]["command"] == "stop"

        asyncio.run(_run())
    finally:
        running.stop()


def test_invalid_access_code_raises_transport_error() -> None:
    sim = PrintSim(total_mm=1000.0, total_seconds=10.0, print_seconds=5.0)
    provider, _built = _provider(sim, printer_access_code="wrong-code", expected_access_code=ACCESS_CODE)

    async def _run() -> None:
        with pytest.raises(ProviderError) as exc_info:
            await provider.start(REMOTE)
        assert exc_info.value.code == "provider_transport_error"

    asyncio.run(_run())


def test_upload_via_ftps_then_start_idle_only(tmp_path) -> None:
    sim = PrintSim(total_mm=1000.0, total_seconds=10.0, print_seconds=5.0)
    provider = BambuLanProvider(host="127.0.0.1", serial="01S00A000000000", access_code=ACCESS_CODE)
    fake_ftp = FakeFtpTls(expected_access_code=ACCESS_CODE)
    provider._ftps_client = lambda: fake_ftp  # instance override; see mock_bambu.py docstring

    local = tmp_path / "demo.gcode"
    local.write_bytes(b"; mock gcode payload\n")

    async def _run() -> None:
        result = await provider.upload(local, "demo.gcode")
        assert result["ok"] is True

    asyncio.run(_run())

    assert fake_ftp.files["cache/demo.gcode"] == b"; mock gcode payload\n"
    # Upload never starts a print by itself — matches the OctoPrint/PrusaLink
    # security contract of "upload != print".
    assert sim.state == "standby"


def test_upload_with_wrong_access_code_raises_transport_error(tmp_path) -> None:
    provider = BambuLanProvider(host="127.0.0.1", serial="01S00A000000000", access_code="wrong")
    fake_ftp = FakeFtpTls(expected_access_code=ACCESS_CODE)
    provider._ftps_client = lambda: fake_ftp

    local = tmp_path / "demo.gcode"
    local.write_bytes(b"; mock gcode payload\n")

    async def _run() -> None:
        with pytest.raises(ProviderError) as exc_info:
            await provider.upload(local, "demo.gcode")
        assert exc_info.value.code == "provider_transport_error"

    asyncio.run(_run())
