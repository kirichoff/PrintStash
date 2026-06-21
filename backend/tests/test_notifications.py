"""Coverage for the notification outbox: enqueue, dispatch, and hub edge-triggers.

Network is always mocked at ``get_http_client``; the in-memory test engine
(see conftest) backs both the ``db_session`` fixture and the dispatcher's own
sessions, so enqueue and delivery share one DB.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
    NotificationTarget,
    Printer,
    PrinterStatus,
)
from app.services import notifications
from app.services.printer_hub import PrinterHub
from app.services.runtime_config import set_notifications_enabled


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _channel(session, *, events, target=NotificationTarget.WEBHOOK, config=None,
             printer_ids=None, enabled=True, name="ch"):
    ch = NotificationChannel(
        name=name,
        target=target,
        enabled=enabled,
        config_json=json.dumps(config or {"url": "https://example.com/hook"}),
        events_json=json.dumps([e.value for e in events]),
        printer_ids_json=json.dumps(printer_ids) if printer_ids is not None else None,
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def _deliveries(session, channel_id=None):
    rows = session.exec(__import__("sqlmodel").select(NotificationDelivery)).all()
    return [d for d in rows if channel_id is None or d.channel_id == channel_id]


def _http_returning(status_code=200, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    client = MagicMock()
    client.request = AsyncMock(return_value=resp)
    return client


# --------------------------------------------------------------------------- #
# backoff schedule
# --------------------------------------------------------------------------- #


def test_backoff_schedule_then_exhaustion():
    assert [notifications.next_retry_delay(a) for a in (1, 2, 3, 4)] == [30, 120, 600, 1800]
    assert notifications.next_retry_delay(5) is None


# --------------------------------------------------------------------------- #
# enqueue (transactional outbox)
# --------------------------------------------------------------------------- #


def test_enqueue_noop_when_master_switch_off(db_session):
    _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE])
    n = notifications.enqueue_for_event(
        db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=1
    )
    db_session.commit()
    assert n == 0
    assert _deliveries(db_session) == []


def test_enqueue_one_per_matching_channel(db_session):
    set_notifications_enabled(db_session, True)
    _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE], name="a")
    _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE], name="b")
    _channel(db_session, events=[NotificationEventType.PRINT_COMPLETED], name="other")
    n = notifications.enqueue_for_event(
        db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=7
    )
    db_session.commit()
    assert n == 2  # only the two offline-subscribed channels
    assert len(_deliveries(db_session)) == 2


def test_enqueue_skips_disabled_channel(db_session):
    set_notifications_enabled(db_session, True)
    _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE], enabled=False)
    n = notifications.enqueue_for_event(
        db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=1
    )
    db_session.commit()
    assert n == 0


def test_enqueue_respects_printer_scope(db_session):
    set_notifications_enabled(db_session, True)
    _channel(
        db_session,
        events=[NotificationEventType.PRINTER_OFFLINE],
        printer_ids=[5],
        name="scoped",
    )
    assert (
        notifications.enqueue_for_event(
            db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=9
        )
        == 0
    )
    assert (
        notifications.enqueue_for_event(
            db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=5
        )
        == 1
    )


def test_enqueue_empty_scope_means_all_printers(db_session):
    set_notifications_enabled(db_session, True)
    _channel(
        db_session,
        events=[NotificationEventType.PRINTER_OFFLINE],
        printer_ids=[],  # empty list == no restriction
    )
    assert (
        notifications.enqueue_for_event(
            db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=123
        )
        == 1
    )


# --------------------------------------------------------------------------- #
# dispatcher
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_dispatch_success_marks_sent_and_channel_status(db_session):
    set_notifications_enabled(db_session, True)
    ch = _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE])
    notifications.enqueue_for_event(
        db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=1
    )
    db_session.commit()

    with patch.object(notifications, "get_http_client", return_value=_http_returning(204)):
        attempted = await notifications.dispatch_due()
    assert attempted == 1

    db_session.expire_all()
    delivery = _deliveries(db_session, ch.id)[0]
    assert delivery.status == NotificationDeliveryStatus.SENT
    assert delivery.attempts == 1
    db_session.refresh(ch)
    assert ch.last_status == "sent"
    assert ch.last_delivered_at is not None


@pytest.mark.asyncio
async def test_dispatch_http_error_retries_with_backoff(db_session):
    set_notifications_enabled(db_session, True)
    ch = _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE])
    notifications.enqueue_for_event(
        db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=1
    )
    db_session.commit()

    with patch.object(notifications, "get_http_client", return_value=_http_returning(500, "boom")):
        await notifications.dispatch_due()

    db_session.expire_all()
    delivery = _deliveries(db_session, ch.id)[0]
    assert delivery.status == NotificationDeliveryStatus.PENDING  # will retry
    assert delivery.attempts == 1
    assert "HTTP 500" in (delivery.last_error or "")
    assert delivery.next_retry_at > delivery.created_at  # backed off


@pytest.mark.asyncio
async def test_dispatch_marks_failed_after_exhausting_retries(db_session):
    set_notifications_enabled(db_session, True)
    ch = _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE])
    notifications.enqueue_for_event(
        db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=1
    )
    db_session.commit()
    delivery_id = _deliveries(db_session, ch.id)[0].id

    # Force the delivery to its last allowed attempt, then fail once more.
    delivery = db_session.get(NotificationDelivery, delivery_id)
    delivery.attempts = notifications._MAX_ATTEMPTS - 1
    db_session.add(delivery)
    db_session.commit()

    with patch.object(notifications, "get_http_client", return_value=_http_returning(500)):
        await notifications.dispatch_due()

    db_session.expire_all()
    delivery = db_session.get(NotificationDelivery, delivery_id)
    assert delivery.status == NotificationDeliveryStatus.FAILED


@pytest.mark.asyncio
async def test_dispatch_render_error_fails_without_network(db_session):
    set_notifications_enabled(db_session, True)
    # Telegram channel missing chat_id -> RenderError, no HTTP call.
    ch = _channel(
        db_session,
        events=[NotificationEventType.PRINTER_OFFLINE],
        target=NotificationTarget.TELEGRAM,
        config={"bot_token": "t"},
    )
    notifications.enqueue_for_event(
        db_session, NotificationEventType.PRINTER_OFFLINE, printer_id=1
    )
    db_session.commit()

    client = _http_returning(200)
    with patch.object(notifications, "get_http_client", return_value=client):
        await notifications.dispatch_due()
    client.request.assert_not_called()

    db_session.expire_all()
    delivery = _deliveries(db_session, ch.id)[0]
    assert delivery.status == NotificationDeliveryStatus.FAILED


# --------------------------------------------------------------------------- #
# hub edge-triggers
# --------------------------------------------------------------------------- #


def test_offline_edge_fires_once_per_transition(db_session):
    set_notifications_enabled(db_session, True)
    p = Printer(name="Ender", moonraker_url="http://x", status=PrinterStatus.READY)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE])

    PrinterHub._mark_status_db(p.id, PrinterStatus.OFFLINE, None)
    PrinterHub._mark_status_db(p.id, PrinterStatus.OFFLINE, None)  # no re-fire
    db_session.expire_all()
    assert len(_deliveries(db_session)) == 1

    # Recover then drop again -> a second, distinct event.
    PrinterHub._mark_status_db(p.id, PrinterStatus.READY, None)
    PrinterHub._mark_status_db(p.id, PrinterStatus.OFFLINE, None)
    db_session.expire_all()
    assert len(_deliveries(db_session)) == 2


def test_print_completed_fires_once_and_is_idempotent(db_session):
    set_notifications_enabled(db_session, True)
    p = Printer(name="Ender", moonraker_url="http://x", status=PrinterStatus.PRINTING)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    _channel(db_session, events=[NotificationEventType.PRINT_COMPLETED])

    stats = {"total_duration": 3600, "filament_used": 1000, "filename": "x.gcode"}
    PrinterHub._sync_active_job_db(p.id, "complete", "x.gcode", 1.0, stats)
    PrinterHub._sync_active_job_db(p.id, "complete", "x.gcode", 1.0, stats)  # idempotent
    db_session.expire_all()
    deliveries = _deliveries(db_session)
    assert len(deliveries) == 1
    assert deliveries[0].event_type == NotificationEventType.PRINT_COMPLETED
    assert deliveries[0].print_job_id is not None


def test_cancelled_emits_distinct_event(db_session):
    set_notifications_enabled(db_session, True)
    p = Printer(name="Ender", moonraker_url="http://x", status=PrinterStatus.PRINTING)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    # Channel only wants completions, not cancellations -> nothing enqueued.
    _channel(db_session, events=[NotificationEventType.PRINT_COMPLETED])

    stats = {"filename": "y.gcode"}
    PrinterHub._sync_active_job_db(p.id, "cancelled", "y.gcode", 0.4, stats)
    db_session.expire_all()
    assert _deliveries(db_session) == []


def test_offline_not_fired_from_unknown(db_session):
    set_notifications_enabled(db_session, True)
    p = Printer(name="Ender", moonraker_url="http://x", status=PrinterStatus.UNKNOWN)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    _channel(db_session, events=[NotificationEventType.PRINTER_OFFLINE])

    PrinterHub._mark_status_db(p.id, PrinterStatus.OFFLINE, None)
    db_session.expire_all()
    assert _deliveries(db_session) == []
