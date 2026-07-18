from __future__ import annotations

from typing import List, Tuple

from pydantic import BaseModel


class PlateObjectRead(BaseModel):
    """One object on a plate: where to fetch its STL, its size and placement."""

    plate: int
    index: int
    name: str | None = None
    bbox_mm: Tuple[float, float, float]
    origin_mm: Tuple[float, float, float]
    stl_url: str


class PlateRead(BaseModel):
    index: int
    objects: List[PlateObjectRead]


class PlateLayoutRead(BaseModel):
    file_id: int
    plate_count: int
    object_count: int
    plates: List[PlateRead]
