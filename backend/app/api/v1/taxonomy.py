"""Categories (hierarchical) and tags (flat) — browse, create, delete.

The model-count queries are intentionally per-row (N+1) here; with the
hundreds-of-rows scale this endpoint deals with, the simpler code wins.
Stage 4 may switch to a single aggregate JOIN if that ever changes.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.http import get_or_404
from app.core.security import require_auth
from app.core.time import utcnow
from app.db.models import Category, Model, ModelTagLink, Tag
from app.db.session import get_session
from app.schemas.models import CategoryCreate, CategoryRead, TagCreate, TagRead
from app.services.taxonomy import slugify

router = APIRouter(tags=["taxonomy"])


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def _category_model_count(session: Session, path: str) -> int:
    matching_cat_ids = select(Category.id).where(
        (Category.path == path) | (Category.path.startswith(path + "/"))
    )
    count = session.exec(
        select(func.count(Model.id)).where(
            Model.deleted_at.is_(None),
            Model.category_id.in_(matching_cat_ids),
        )
    ).one()
    return int(count or 0)


@router.get(
    "/categories",
    response_model=List[CategoryRead],
    summary="List all categories with model counts",
)
def list_categories(session: Session = Depends(get_session)) -> List[CategoryRead]:
    cats = session.exec(
        select(Category).where(Category.deleted_at.is_(None)).order_by(Category.path)  # type: ignore[union-attr]
    ).all()
    return [
        CategoryRead(
            id=c.id,
            name=c.name,
            slug=c.slug,
            path=c.path,
            parent_id=c.parent_id,
            model_count=_category_model_count(session, c.path),
        )
        for c in cats
    ]


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
    summary="Create a new category",
)
def create_category(
    payload: CategoryCreate,
    session: Session = Depends(get_session),
) -> CategoryRead:
    slug = slugify(payload.name)
    if session.exec(select(Category).where(Category.slug == slug)).first():
        raise HTTPException(status_code=409, detail="category_already_exists")

    path = slug
    if payload.parent_id is not None:
        parent = get_or_404(session, Category, payload.parent_id, "parent_not_found")
        path = f"{parent.path}/{slug}"

    cat = Category(name=payload.name, slug=slug, parent_id=payload.parent_id, path=path)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return CategoryRead(
        id=cat.id,
        name=cat.name,
        slug=cat.slug,
        path=cat.path,
        parent_id=cat.parent_id,
        model_count=0,
    )


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_auth)],
    summary="Delete a category",
)
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
) -> Response:
    cat = get_or_404(session, Category, category_id, "category_not_found")

    if session.exec(select(Category).where(Category.parent_id == category_id)).first():
        raise HTTPException(status_code=409, detail="category_has_children")
    if _category_model_count(session, cat.path):
        raise HTTPException(status_code=409, detail="category_has_models")

    cat.deleted_at = utcnow()
    session.add(cat)
    session.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def _tag_model_count(session: Session, tag_id: int) -> int:
    count = session.exec(
        select(func.count(ModelTagLink.model_id))
        .join(Model, Model.id == ModelTagLink.model_id)
        .where(ModelTagLink.tag_id == tag_id, Model.deleted_at.is_(None))
    ).one()
    return int(count or 0)


@router.get(
    "/tags",
    response_model=List[TagRead],
    summary="List all tags with model counts",
)
def list_tags(session: Session = Depends(get_session)) -> List[TagRead]:
    tags = session.exec(
        select(Tag).where(Tag.deleted_at.is_(None)).order_by(Tag.name)  # type: ignore[union-attr]
    ).all()
    return [
        TagRead(
            id=t.id,
            name=t.name,
            slug=t.slug,
            model_count=_tag_model_count(session, t.id),
        )
        for t in tags
    ]


@router.post(
    "/tags",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
    summary="Create a new tag",
)
def create_tag(
    payload: TagCreate,
    session: Session = Depends(get_session),
) -> TagRead:
    slug = slugify(payload.name)
    if session.exec(select(Tag).where(Tag.slug == slug)).first():
        raise HTTPException(status_code=409, detail="tag_already_exists")

    tag = Tag(name=payload.name, slug=slug)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return TagRead(id=tag.id, name=tag.name, slug=tag.slug, model_count=0)


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_auth)],
    summary="Delete a tag",
)
def delete_tag(
    tag_id: int,
    session: Session = Depends(get_session),
) -> Response:
    from sqlmodel import delete

    tag = get_or_404(session, Tag, tag_id, "tag_not_found")
    session.exec(delete(ModelTagLink).where(ModelTagLink.tag_id == tag_id))  # type: ignore[call-overload]
    tag.deleted_at = utcnow()
    session.add(tag)
    session.commit()
    return Response(status_code=204)
