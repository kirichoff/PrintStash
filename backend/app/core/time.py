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
