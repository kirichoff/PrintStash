"""Process-wide configuration, sourced from ``VAULT_*`` environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VAULT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage
    data_dir: Path = Path("/data/files")
    thumb_dir: Path = Path("/data/thumbs")

    # Database
    db_url: str = "sqlite:////data/db/nexus3d.sqlite"

    # Auth — Stage 1 uses a shared API key on writes; Stage 3+ adds JWT login.
    # The very first user is created by the web-based setup wizard
    # (POST /api/v1/setup) — there is no env-driven default admin.
    api_key: str = "changeme"
    jwt_secret: str = "changeme_jwt_secret_please_change"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Limits
    max_upload_mb: int = 512

    # Observability
    log_level: str = "INFO"

    # App
    app_name: str = "PrintStash"
    app_version: str = "0.1.0"

    @property
    def incoming_dir(self) -> Path:
        return self.data_dir / "_incoming"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()


def _sqlite_db_path(db_url: str) -> Path | None:
    """Return the on-disk path for a sqlite URL, or ``None`` for in-memory/other."""
    if not db_url.startswith("sqlite"):
        return None
    database = make_url(db_url).database
    if not database or database == ":memory:":
        return None
    return Path(database)


def ensure_dirs() -> None:
    """Create required storage directories at startup. Idempotent."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.thumb_dir.mkdir(parents=True, exist_ok=True)
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)

    db_path = _sqlite_db_path(settings.db_url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
