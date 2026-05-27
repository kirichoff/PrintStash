from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.db.models import PrintJobState, PrinterStatus


class PrinterCreate(BaseModel):
    name: str
    moonraker_url: str
    api_key: Optional[str] = None
    notes: Optional[str] = None
    group: Optional[str] = None


class PrinterUpdate(BaseModel):
    name: Optional[str] = None
    moonraker_url: Optional[str] = None
    api_key: Optional[str] = None
    notes: Optional[str] = None
    group: Optional[str] = None


class PrinterRead(BaseModel):
    id: int
    name: str
    moonraker_url: str
    has_api_key: bool
    notes: Optional[str] = None
    group: Optional[str] = None
    status: PrinterStatus
    last_seen_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SendToPrinter(BaseModel):
    file_id: int
    start_print: bool = False
    remote_filename: Optional[str] = None


class PrintJobRead(BaseModel):
    id: int
    printer_id: int
    file_id: int
    model_id: int
    remote_filename: str
    state: PrintJobState
    progress: float
    source: str = "vault"
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
