"""Fakes for ``BambuLanProvider``'s three real transports.

Bambu LAN mode is not one protocol: status polling hits a plain HTTPS REST
endpoint (self-signed cert, verified off — see ``BambuLanProvider.query_status``),
commands go out over MQTT built fresh per-call in ``_mqtt_client()``, and
uploads go over implicit FTPS via ``_ftps_client()``. Neither MQTT nor FTPS
client is constructor-injectable in production code, so these fakes are
swapped in by monkeypatching the *instance* methods
(``provider._mqtt_client = lambda: fake``, same for ``_ftps_client``) —
regular methods, not descriptors, so an instance attribute cleanly shadows
the class method for the object under test.

The status endpoint, by contrast, *is* reachable over a real loopback
socket: ``query_status`` always sets ``verify=False`` (Bambu ships a
device-local self-signed cert with no CA), so any self-signed cert works —
``start_status_server`` below runs one on real TLS, exercising the actual
httpx call the provider makes.
"""

from __future__ import annotations

import datetime
import json
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI

from .print_sim import PrintSim

# -- Bambu print.gcode_state <-> PrintSim.state, mirrors
# BambuLanProvider._STATE_TO_MOONRAKER inverted. --------------------------
_SIM_TO_BAMBU_STATE = {
    "standby": "IDLE",
    "printing": "RUNNING",
    "paused": "PAUSE",
    "complete": "FINISH",
    "cancelled": "FINISH",  # Bambu has no distinct cancelled gcode_state.
    "error": "FAILED",
}


def _status_report(sim: PrintSim) -> dict[str, Any]:
    sim.progress()
    return {
        "print": {
            "gcode_state": _SIM_TO_BAMBU_STATE.get(sim.state, "IDLE"),
            "mc_percent": round(sim.progress() * 100),
            "subtask_name": sim.filename or None,
            "print_error": sim.message or "",
        }
    }


def create_status_app(sim: PrintSim) -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/status")
    async def status() -> dict:
        return _status_report(sim)

    return app


def _generate_self_signed_cert(tmpdir: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mock-bambu")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_path = tmpdir / "cert.pem"
    key_path = tmpdir / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


@dataclass
class RunningTlsServer:
    base_url: str
    port: int
    _server: Any
    _thread: threading.Thread
    _tmpdir: tempfile.TemporaryDirectory

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)
        self._tmpdir.cleanup()


def start_status_server(sim: PrintSim) -> RunningTlsServer:
    """Run the Bambu status REST app on real loopback TLS (self-signed cert).

    ``BambuLanProvider.query_status`` hardcodes port 6000 (no injectable
    transport, unlike the PrusaLink/OctoPrint clients) — this binds the fake
    to that literal port on loopback rather than a free one, so the real
    client code reaches it unmodified.
    """
    import uvicorn

    tmpdir = tempfile.TemporaryDirectory()
    cert_path, key_path = _generate_self_signed_cert(Path(tmpdir.name))
    port = 6000
    app = create_status_app(sim)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
        ssl_certfile=str(cert_path),
        ssl_keyfile=str(key_path),
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("mock bambu status server failed to start within 10s")
        time.sleep(0.02)
    return RunningTlsServer(
        base_url=f"https://127.0.0.1:{port}", port=port, _server=server, _thread=thread, _tmpdir=tmpdir
    )


# -- Fake MQTT client (paho v2 surface: username_pw_set/tls_set/connect/
# loop_start/publish/loop_stop/disconnect) ---------------------------------


class _FakePublishInfo:
    def __init__(self, published: bool) -> None:
        self._published = published

    def wait_for_publish(self, timeout: float | None = None) -> None:
        return None

    def is_published(self) -> bool:
        return self._published


class FakeMqttClient:
    """Drives a ``PrintSim`` from the same command payloads ``_send_command`` sends.

    Standing in for the whole of ``_mqtt_client()`` (not just ``mqtt.Client``),
    so the real method's own ``username_pw_set``/``tls_set`` calls never run —
    the access code the "printer" checks against is passed in directly at
    construction instead of being captured off a call the fake never sees.
    """

    def __init__(
        self,
        sim: PrintSim,
        *,
        attempted_access_code: Optional[str] = None,
        expected_access_code: Optional[str] = None,
    ) -> None:
        self.sim = sim
        self.attempted_access_code = attempted_access_code
        self.expected_access_code = expected_access_code
        self.published: list[dict[str, Any]] = []

    def username_pw_set(self, username: str, password: Optional[str] = None) -> None:
        return None

    def tls_set(self, *args: Any, **kwargs: Any) -> None:
        return None

    def connect(self, host: str, port: int = 8883, keepalive: int = 30) -> None:
        if (
            self.expected_access_code is not None
            and self.attempted_access_code != self.expected_access_code
        ):
            raise ConnectionRefusedError("not authorised")

    def loop_start(self) -> None:
        return None

    def loop_stop(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False) -> _FakePublishInfo:
        body = json.loads(payload)
        self.published.append(body)
        command = body.get("print", {}).get("command")
        if command == "gcode_file":
            param = body["print"]["param"]
            filename = param.rsplit("/", 1)[-1]
            self.sim.start(filename)
        elif command == "pause":
            self.sim.pause()
        elif command == "resume":
            self.sim.resume()
        elif command == "stop":
            self.sim.cancel()
        return _FakePublishInfo(published=True)


def make_mqtt_factory(
    sim: PrintSim,
    *,
    attempted_access_code: Optional[str] = None,
    expected_access_code: Optional[str] = None,
) -> tuple[Callable[[], FakeMqttClient], list[FakeMqttClient]]:
    """Factory to monkeypatch onto ``provider._mqtt_client``; records every client built."""
    built: list[FakeMqttClient] = []

    def factory() -> FakeMqttClient:
        client = FakeMqttClient(
            sim,
            attempted_access_code=attempted_access_code,
            expected_access_code=expected_access_code,
        )
        built.append(client)
        return client

    return factory, built


# -- Fake implicit FTPS client (ftplib.FTP_TLS surface used by
# _upload_via_ftps: connect/login/prot_p/storbinary/size/rename/quit/close) -


@dataclass
class FakeFtpTls:
    files: dict[str, bytes] = field(default_factory=dict)
    expected_access_code: Optional[str] = None
    connected_host: Optional[str] = None

    def connect(self, host: str, port: int = 990) -> None:
        self.connected_host = host

    def login(self, user: str, passwd: str = "") -> None:
        if self.expected_access_code is not None and passwd != self.expected_access_code:
            raise PermissionError("530 Login incorrect")

    def prot_p(self) -> None:
        return None

    def storbinary(self, cmd: str, source) -> None:  # noqa: ANN001 - matches ftplib signature
        _, _, path = cmd.partition(" ")
        self.files[path] = source.read()

    def size(self, path: str) -> Optional[int]:
        data = self.files.get(path)
        return len(data) if data is not None else None

    def rename(self, from_path: str, to_path: str) -> None:
        self.files[to_path] = self.files.pop(from_path)

    def quit(self) -> None:
        return None

    def close(self) -> None:
        return None
