"""Categories & tags -- browse, create, and delete."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.security import require_api_key
from app.db.models import Category, Model, ModelTagLink, Tag
from app.db.session import get_session
from app.schemas.models import CategoryCreate, CategoryRead, TagCreate, TagRead
from app.services.taxonomy import slugify

router = APIRouter(tags=["taxonomy"])


# -- Categories --------------------------------------------------------------


@router.get(
    "/categories",
    response_model=List[CategoryRead],
    summary="List all categories with model counts",
)
def list_categories(session: Session = Depends(get_session)) -> List[CategoryRead]:
    cats = session.exec(select(Category).order_by(Category.path)).all()
    out: List[CategoryRead] = []
    for c in cats:
        count = session.exec(
            select(func.count(Model.id)).where(
                Model.deleted_at.is_(None),
                (Model.category == c.path) | (Model.category.startswith(c.path + "/")),
            )
        ).one()
        out.append(
            CategoryRead(
                id=c.id,
                name=c.name,
                slug=c.slug,
                path=c.path,
                parent_id=c.parent_id,
                model_count=int(count or 0),
            )
        )
    return out


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
    summary="Create a new category",
)
def create_category(
    payload: CategoryCreate,
    session: Session = Depends(get_session),
) -> CategoryRead:
    slug = slugify(payload.name)
    existing = session.exec(select(Category).where(Category.slug == slug)).first()
    if existing:
        raise HTTPException(status_code=409, detail="category_already_exists")

    path = slug
    if payload.parent_id is not None:
        parent = session.get(Category, payload.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="parent_not_found")
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
    dependencies=[Depends(require_api_key)],
    summary="Delete a category",
)
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
) -> Response:
    cat = session.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="category_not_found")

    children = session.exec(
        select(Category).where(Category.parent_id == category_id)
    ).all()
    if children:
        raise HTTPException(status_code=409, detail="category_has_children")

    model_count = session.exec(
        select(func.count(Model.id)).where(
            Model.deleted_at.is_(None),
            (Model.category == cat.path) | (Model.category.startswith(cat.path + "/")),
        )
    ).one()
    if model_count:
        raise HTTPException(status_code=409, detail="category_has_models")

    session.delete(cat)
    session.commit()
    return Response(status_code=204)


# -- Tags --------------------------------------------------------------------


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
            .where(ModelTagLink.tag_id == t.id, Model.deleted_at.is_(None))
        ).one()
        out.append(
            TagRead(
                id=t.id,
                name=t.name,
                slug=t.slug,
                model_count=int(count or 0),
            )
        )
    return out


@router.post(
    "/tags",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
    summary="Create a new tag",
)
def create_tag(
    payload: TagCreate,
    session: Session = Depends(get_session),
) -> TagRead:
    slug = slugify(payload.name)
    existing = session.exec(select(Tag).where(Tag.slug == slug)).first()
    if existing:
        raise HTTPException(status_code=409, detail="tag_already_exists")

    tag = Tag(name=payload.name, slug=slug)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return TagRead(
        id=tag.id,
        name=tag.name,
        slug=tag.slug,
        model_count=0,
    )


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_api_key)],
    summary="Delete a tag",
)
def delete_tag(
    tag_id: int,
    session: Session = Depends(get_session),
) -> Response:
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="tag_not_found")

    for link in session.exec(
        select(ModelTagLink).where(ModelTagLink.tag_id == tag_id)
    ).all():
        session.delete(link)
    session.flush()
    session.delete(tag)
    session.commit()
    return Response(status_code=204)
