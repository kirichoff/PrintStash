"""Time helpers. Use :func:`utcnow` everywhere — never ``datetime.utcnow``."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC ``datetime``.

    ``datetime.utcnow()`` is deprecated since Python 3.12 because it returns a
    naive datetime, which causes subtle bugs when serialised or compared with
    aware datetimes coming from the DB or external APIs.
    """
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """Normalise a ``datetime`` to timezone-aware UTC.

    Datetime columns persist as naive values (no ``timezone=True``), so a value
    read back from the DB is naive even though we always *write* aware UTC. Use
    this before any Python-side arithmetic/comparison against :func:`utcnow` to
    avoid ``can't subtract offset-naive and offset-aware datetimes``.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
