"""Small HTTP helpers shared across routers."""

from __future__ import annotations

from typing import Type, TypeVar

from fastapi import HTTPException
from sqlmodel import Session, SQLModel

T = TypeVar("T", bound=SQLModel)


def get_or_404(session: Session, model_cls: Type[T], pk: int, detail: str) -> T:
    """Fetch a row by primary key or raise ``HTTPException(404, detail)``."""
    obj = session.get(model_cls, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj
