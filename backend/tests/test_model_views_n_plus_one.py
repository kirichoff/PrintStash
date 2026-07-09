"""Listing a page of models must cost a fixed number of queries.

``effective_role`` was resolved per row, and each resolution ran two queries (the
collection, then the grants). A 50-model page therefore issued ~100 extra
queries, all returning the same handful of grants.
"""

from __future__ import annotations

from typing import Callable

import pytest
from sqlalchemy import event
from sqlmodel import Session

from app.db.models import CollectionPermission, CollectionRole, Model, User
from app.services import model_views, taxonomy
from app.services.auth import hash_password


def _user(session: Session, username: str, *, superuser: bool = False) -> User:
    user = User(
        username=username,
        hashed_password=hash_password("Password123"),
        is_active=True,
        is_superuser=superuser,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _seed_models(session: Session, count: int, collection_id: int) -> None:
    for i in range(count):
        session.add(
            Model(
                name=f"Model {i}",
                slug=f"model-{i}",
                hash=f"{i:064d}",
                collection_id=collection_id,
            )
        )
    session.commit()


def _count_queries(session: Session, fn: Callable[[], object]) -> int:
    statements: list[str] = []

    def _record(conn, cursor, statement, *args):  # noqa: ANN001
        statements.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", _record)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return len(statements)


@pytest.mark.parametrize("superuser", [False, True])
def test_list_query_count_is_independent_of_page_size(
    db_session: Session, superuser: bool
) -> None:
    collection = taxonomy.resolve_or_create_collection(db_session, "Parts")
    assert collection is not None
    user = _user(db_session, f"lister-{superuser}", superuser=superuser)
    if not superuser:
        db_session.add(
            CollectionPermission(
                user_id=user.id,
                collection_id=collection.id,
                role=CollectionRole.EDIT,
            )
        )
        db_session.commit()

    _seed_models(db_session, 2, collection.id)
    small = _count_queries(
        db_session, lambda: model_views.list_items(db_session, user, limit=100)
    )

    _seed_models_more = 30
    for i in range(_seed_models_more):
        db_session.add(
            Model(
                name=f"Extra {i}",
                slug=f"extra-{i}",
                hash=f"e{i:063d}",
                collection_id=collection.id,
            )
        )
    db_session.commit()

    large = _count_queries(
        db_session, lambda: model_views.list_items(db_session, user, limit=100)
    )

    assert large == small, (
        f"query count grew with page size ({small} -> {large}): a per-row lookup "
        "is running inside the listing loop"
    )


def test_effective_role_is_still_correct_per_row(db_session: Session) -> None:
    """Batching must not flatten roles: each model reports its own inherited role."""
    parts = taxonomy.resolve_or_create_collection(db_session, "Parts")
    toys = taxonomy.resolve_or_create_collection(db_session, "Toys")
    assert parts is not None and toys is not None
    user = _user(db_session, "mixed")
    db_session.add(
        CollectionPermission(
            user_id=user.id, collection_id=parts.id, role=CollectionRole.ADMIN
        )
    )
    db_session.add(
        CollectionPermission(
            user_id=user.id, collection_id=toys.id, role=CollectionRole.VIEW
        )
    )
    db_session.commit()

    db_session.add(Model(name="P", slug="p", hash="p" * 64, collection_id=parts.id))
    db_session.add(Model(name="T", slug="t", hash="t" * 64, collection_id=toys.id))
    db_session.commit()

    items = model_views.list_items(db_session, user, limit=100)
    roles = {item.name: item.effective_role for item in items}

    assert roles["P"] == CollectionRole.ADMIN
    assert roles["T"] == CollectionRole.VIEW
