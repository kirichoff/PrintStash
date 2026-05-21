"""Read-only endpoints for browsing the category tree and tag list."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from app.db.models import Category, Model, ModelTagLink, Tag
from app.db.session import get_session
from app.schemas.models import CategoryRead, TagRead

router = APIRouter(tags=["taxonomy"])


@router.get(
    "/categories",
    response_model=List[CategoryRead],
    summary="List all categories with model counts",
)
def list_categories(session: Session = Depends(get_session)) -> List[CategoryRead]:
    cats = session.exec(select(Category).order_by(Category.path)).all()
    out: List[CategoryRead] = []
    for c in cats:
        # Count models whose category path equals this path OR is a descendant.
        count = session.exec(
            select(func.count(Model.id)).where(
                Model.deleted_at.is_(None),  # type: ignore[union-attr]
                (Model.category == c.path)
                | (Model.category.startswith(c.path + "/")),  # type: ignore[attr-defined]
            )
        ).one()
        out.append(
            CategoryRead(
                id=c.id,  # type: ignore[arg-type]
                name=c.name,
                slug=c.slug,
                path=c.path,
                parent_id=c.parent_id,
                model_count=int(count or 0),
            )
        )
    return out


@router.get(
    "/tags",
    response_model=List[TagRead],
    summary="List all tags with model counts",
)
def list_tags(session: Session = Depends(get_session)) -> List[TagRead]:
    tags = session.exec(select(Tag).order_by(Tag.name)).all()
    out: List[TagRead] = []
    for t in tags:
        count = session.exec(
            select(func.count(ModelTagLink.model_id))
            .join(Model, Model.id == ModelTagLink.model_id)
            .where(ModelTagLink.tag_id == t.id, Model.deleted_at.is_(None))  # type: ignore[union-attr]
        ).one()
        out.append(
            TagRead(
                id=t.id,  # type: ignore[arg-type]
                name=t.name,
                slug=t.slug,
                model_count=int(count or 0),
            )
        )
    return out
