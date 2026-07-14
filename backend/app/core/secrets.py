"""Authenticated encryption for credentials persisted by PrintStash."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_PREFIX = "enc:v1:"


def _key_material() -> bytes:
    configured = str(settings.secrets_key).strip()
    if configured:
        return configured.encode()

    path = Path(settings.secrets_key_file)
    try:
        return path.read_bytes().strip()
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        generated = base64.urlsafe_b64encode(os.urandom(32))
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return path.read_bytes().strip()
        with os.fdopen(fd, "wb") as handle:
            handle.write(generated + b"\n")
        return generated


def _fernet() -> Fernet:
    derived = hashlib.sha256(_key_material()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value.startswith(_PREFIX):
        return value
    token = _fernet().encrypt(value.encode()).decode()
    return f"{_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None or not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX) :].encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "stored credential cannot be decrypted; restore VAULT_SECRETS_KEY "
            "or the secrets key file"
        ) from exc
