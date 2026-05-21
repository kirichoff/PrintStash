from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


JobState = Literal["pending", "running", "completed", "failed"]


class IngestResponse(BaseModel):
    """Returned immediately from POST /ingest/orca."""

    job_id: str
    state: JobState
    message: str = "ingestion queued"


class IngestJobStatus(BaseModel):
    job_id: str
    state: JobState
    model_id: Optional[int] = None
    file_id: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
