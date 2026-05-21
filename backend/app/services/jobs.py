"""In-process job registry for Stage 1 background tasks.

Stage 3+ will swap this for Redis/Celery. The interface is intentionally
narrow so the swap is mechanical.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Dict, Optional

from app.schemas.ingest import IngestJobStatus, JobState


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: Dict[str, IngestJobStatus] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = IngestJobStatus(
                job_id=job_id,
                state="pending",
            )
        return job_id

    def update(
        self,
        job_id: str,
        *,
        state: Optional[JobState] = None,
        model_id: Optional[int] = None,
        file_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if state is not None:
                job.state = state
                if state == "running" and job.started_at is None:
                    job.started_at = datetime.utcnow()
                if state in ("completed", "failed"):
                    job.finished_at = datetime.utcnow()
            if model_id is not None:
                job.model_id = model_id
            if file_id is not None:
                job.file_id = file_id
            if error is not None:
                job.error = error

    def get(self, job_id: str) -> Optional[IngestJobStatus]:
        with self._lock:
            return self._jobs.get(job_id)


registry = JobRegistry()
