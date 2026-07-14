from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SavedViewFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection: Optional[str] = Field(default=None, max_length=512)
    direct: bool = False
    tag: list[str] = Field(default_factory=list, max_length=64)
    q: Optional[str] = Field(default=None, max_length=255)
    printer_id: Optional[int] = Field(default=None, gt=0)
    printer_presence: Optional[Literal["any", "none"]] = None
    favorites: bool = False


class SavedViewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    filters: SavedViewFilters


class SavedViewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    filters: Optional[SavedViewFilters] = None


class SavedViewRead(BaseModel):
    id: int
    name: str
    filters: SavedViewFilters
    created_at: datetime
    updated_at: datetime


class ModelStarRead(BaseModel):
    model_id: int
    starred: bool
