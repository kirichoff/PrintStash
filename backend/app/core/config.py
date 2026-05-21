from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration, sourced from environment variables."""

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

    # Auth (Stage 1: shared API key on write endpoints)
    api_key: str = "changeme"

    # Limits
    max_upload_mb: int = 512

    # Observability
    log_level: str = "INFO"

    # App
    app_name: str = "Nexus3D Vault"
    app_version: str = "0.1.0"

    @property
    def incoming_dir(self) -> Path:
        return self.data_dir / "_incoming"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()


def ensure_dirs() -> None:
    """Create required storage directories at startup."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.thumb_dir.mkdir(parents=True, exist_ok=True)
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)

    # If db_url points at a sqlite file under /data/db, ensure the parent exists.
    if settings.db_url.startswith("sqlite"):
        # Strip 'sqlite:///' or 'sqlite:////' prefix safely.
        raw = settings.db_url.split("sqlite:///", 1)[-1]
        # leading '/' on absolute URLs is preserved by split above for sqlite:////...
        db_path = Path(raw if raw.startswith("/") else f"/{raw}") if settings.db_url.startswith("sqlite:////") else Path(raw)
        db_path.parent.mkdir(parents=True, exist_ok=True)
