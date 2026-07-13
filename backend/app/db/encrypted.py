"""SQLAlchemy type that transparently encrypts text at the persistence edge."""

from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from app.core.secrets import decrypt_secret, encrypt_secret


class EncryptedText(TypeDecorator[str]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return encrypt_secret(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        return decrypt_secret(value)
