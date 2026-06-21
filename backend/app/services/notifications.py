"""Outbound notifications: transactional-outbox enqueue + delivery dispatcher.

Two halves:

* :func:`enqueue_for_event` is called **inside** the printer hub's existing DB
  transactions (see :mod:`app.services.printer_hub`). For each enabled channel
  subscribed to the event and matching its printer scope, it adds a
  :class:`NotificationDelivery` row to the *same session*. Because it shares the
  caller's transaction, an event and its deliveries commit atomically — the
  outbox can't be lost — and because the hub edge-triggers state changes, an
  event is enqueued exactly once.

* :func:`run_dispatcher_loop` is a background task started in the app lifespan.
  It polls due deliveries, renders each via :mod:`app.services.notification_renderers`,
  POSTs through the shared HTTP client, and records success / retry / failure
  with exponential backoff, surfacing a "last notification" status on the
  channel for the UI.

All blocking DB work runs in worker threads to keep the event loop free.
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from app.core.http_client import get_http_client
from app.core.logging import get_logger
from app.core.time import utcnow
from app.db.session import get_session_factory
from app.db.models import (
    Model,
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
    NotificationTarget,
    Printer,
    PrintJob,
)
from app.services import notification_renderers as renderers
from app.services.runtime_config import notifications_enabled

logger = get_logger(__name__)

# Config keys whose values are secret-bearing (webhook URLs embed tokens). The
# API masks these on read and preserves them across updates when re-sent blank.
_SECRET_CONFIG_KEYS: Dict[NotificationTarget, set] = {
    NotificationTarget.WEBHOOK: {"url"},
    NotificationTarget.DISCORD: {"url"},
    NotificationTarget.TELEGRAM: {"bot_token"},
    NotificationTarget.NTFY: {"token"},
}

# Backoff (seconds) applied *after* attempt N fails, indexed by N-1. When a
# delivery's attempt count exceeds this list it is marked permanently failed —
# so the schedule below allows ``len + 1`` total attempts.
_BACKOFF_SECONDS: List[int] = [30, 120, 600, 1800]
_MAX_ATTEMPTS = len(_BACKOFF_SECONDS) + 1

# How often the dispatcher wakes to look for due deliveries.
_POLL_INTERVAL_S = 15
# Max deliveries processed per tick (bounds memory / burst load).
_BATCH_SIZE = 50
# Per-request network timeout.
_REQUEST_TIMEOUT_S = 15.0


def next_retry_delay(attempts: int) -> Optional[int]:
    """Seconds to wait before retry after ``attempts`` failures, or ``None`` if exhausted.

    ``attempts`` is the number of attempts already made (1 after the first
    failure). Returns ``None`` once the retry budget is spent so the caller
    marks the delivery permanently failed.
    """
    idx = attempts - 1
    if 0 <= idx < len(_BACKOFF_SECONDS):
        return _BACKOFF_SECONDS[idx]
    return None


# --------------------------------------------------------------------------- #
# Enqueue (runs inside the caller's transaction)
# --------------------------------------------------------------------------- #


def build_context(
    session: Session,
    event_type: NotificationEventType,
    *,
    printer_id: Optional[int],
    job: Optional[PrintJob] = None,
) -> Dict[str, Any]:
    """Assemble the normalised event context dict used by the renderers."""
    printer_name: Optional[str] = None
    if printer_id is not None:
        printer = session.get(Printer, printer_id)
        printer_name = printer.name if printer else None

    ctx: Dict[str, Any] = {
        "event": event_type.value,
        "printer_id": printer_id,
        "printer_name": printer_name,
        "timestamp": utcnow().isoformat().replace("+00:00", "Z"),
    }
    if job is not None:
        model_name: Optional[str] = None
        if job.model_id:
            model = session.get(Model, job.model_id)
            # The external-job sentinel model has no meaningful name; skip it.
            model_name = model.name if model and model.name else None
        ctx.update(
            {
                "job_id": job.id,
                "filename": job.remote_filename,
                "model_name": model_name,
                "duration_s": job.actual_duration_s,
                "filament_used_g": job.filament_used_g,
                "error": job.error,
            }
        )
    return ctx


def _channel_subscribes(
    channel: NotificationChannel,
    event_type: NotificationEventType,
    printer_id: Optional[int],
) -> bool:
    """Whether ``channel`` wants this event for this printer."""
    try:
        events = json.loads(channel.events_json or "[]")
    except (TypeError, ValueError):
        events = []
    if event_type.value not in events:
        return False
    if channel.printer_ids_json:
        try:
            scoped = json.loads(channel.printer_ids_json)
        except (TypeError, ValueError):
            scoped = None
        # A non-empty scope restricts to listed printers (printer_id may be None
        # for printer-less events, which scoped channels then never match).
        if scoped:
            return printer_id in scoped
    return True


def enqueue_for_event(
    session: Session,
    event_type: NotificationEventType,
    *,
    printer_id: Optional[int] = None,
    job: Optional[PrintJob] = None,
) -> int:
    """Add a delivery row per matching channel to ``session`` (no commit).

    Returns the number of deliveries enqueued. No-op (returns 0) while the
    notifications master switch is off or no channel matches. The caller's
    transaction is responsible for committing — that atomicity is the whole
    point of the transactional outbox.
    """
    if not notifications_enabled(session):
        return 0
    channels = session.exec(
        select(NotificationChannel).where(NotificationChannel.enabled == True)  # noqa: E712
    ).all()
    matching = [c for c in channels if _channel_subscribes(c, event_type, printer_id)]
    if not matching:
        return 0

    context = build_context(session, event_type, printer_id=printer_id, job=job)
    context_json = json.dumps(context)
    now = utcnow()
    for channel in matching:
        session.add(
            NotificationDelivery(
                channel_id=channel.id,
                event_type=event_type,
                printer_id=printer_id,
                print_job_id=job.id if job is not None else None,
                context_json=context_json,
                status=NotificationDeliveryStatus.PENDING,
                next_retry_at=now,
            )
        )
    logger.info(
        "enqueued %d notification(s) for %s (printer=%s)",
        len(matching),
        event_type.value,
        printer_id,
    )
    return len(matching)


# --------------------------------------------------------------------------- #
# Dispatcher (background loop)
# --------------------------------------------------------------------------- #


def _claim_due_deliveries() -> List[Dict[str, Any]]:
    """Fetch due deliveries joined with their channel config (thread-side).

    Returns plain dicts (detached from the session) so the async sender doesn't
    touch ORM objects across the thread boundary.
    """
    now = utcnow()
    out: List[Dict[str, Any]] = []
    with get_session_factory().session() as session:
        rows = session.exec(
            select(NotificationDelivery, NotificationChannel)
            .join(
                NotificationChannel,
                NotificationDelivery.channel_id == NotificationChannel.id,  # type: ignore[arg-type]
            )
            .where(
                NotificationDelivery.status == NotificationDeliveryStatus.PENDING,
                NotificationDelivery.next_retry_at <= now,
            )
            .order_by(NotificationDelivery.next_retry_at)  # type: ignore[attr-defined]
            .limit(_BATCH_SIZE)
        ).all()
        for delivery, channel in rows:
            try:
                config = json.loads(channel.config_json or "{}")
            except (TypeError, ValueError):
                config = {}
            try:
                context = json.loads(delivery.context_json or "{}")
            except (TypeError, ValueError):
                context = {}
            out.append(
                {
                    "delivery_id": delivery.id,
                    "channel_id": channel.id,
                    "target": channel.target,
                    "config": config,
                    "context": context,
                    "attempts": delivery.attempts,
                }
            )
    return out


def _record_result(
    delivery_id: int,
    channel_id: int,
    *,
    success: bool,
    error: Optional[str],
    permanent: bool = False,
) -> None:
    """Persist a delivery attempt's outcome + the channel's last-status (thread-side).

    ``permanent`` marks a non-transient failure (e.g. invalid channel config)
    that retrying cannot fix, so the delivery fails immediately without
    consuming the retry budget.
    """
    now = utcnow()
    with get_session_factory().session() as session:
        delivery = session.get(NotificationDelivery, delivery_id)
        channel = session.get(NotificationChannel, channel_id)
        if delivery is None:
            return
        delivery.attempts += 1
        delivery.updated_at = now
        if success:
            delivery.status = NotificationDeliveryStatus.SENT
            delivery.delivered_at = now
            delivery.last_error = None
        else:
            delivery.last_error = (error or "")[:1024]
            delay = None if permanent else next_retry_delay(delivery.attempts)
            if delay is None:
                delivery.status = NotificationDeliveryStatus.FAILED
            else:
                delivery.status = NotificationDeliveryStatus.PENDING
                delivery.next_retry_at = now + timedelta(seconds=delay)
        session.add(delivery)
        if channel is not None:
            channel.last_status = delivery.status.value
            channel.last_error = None if success else (error or "")[:1024]
            if success:
                channel.last_delivered_at = now
            channel.updated_at = now
            session.add(channel)
        session.commit()


async def _send_one(item: Dict[str, Any]) -> None:
    """Render and send a single delivery, then record the outcome."""
    delivery_id = item["delivery_id"]
    channel_id = item["channel_id"]
    try:
        req = renderers.render(item["target"], item["context"], item["config"])
    except renderers.RenderError as exc:
        # Config/render errors are not transient — fail without burning retries.
        await asyncio.to_thread(
            _record_result,
            delivery_id,
            channel_id,
            success=False,
            error=str(exc),
            permanent=True,
        )
        return
    try:
        client = get_http_client()
        resp = await client.request(
            req.method,
            req.url,
            headers=req.headers or None,
            json=req.json,
            content=req.data.encode("utf-8") if req.data is not None else None,
            timeout=_REQUEST_TIMEOUT_S,
        )
        if 200 <= resp.status_code < 300:
            await asyncio.to_thread(
                _record_result, delivery_id, channel_id, success=True, error=None
            )
        else:
            body = (resp.text or "")[:200]
            await asyncio.to_thread(
                _record_result,
                delivery_id,
                channel_id,
                success=False,
                error=f"HTTP {resp.status_code}: {body}",
            )
    except Exception as exc:  # noqa: BLE001 — network boundary
        await asyncio.to_thread(
            _record_result, delivery_id, channel_id, success=False, error=str(exc)
        )


async def dispatch_due() -> int:
    """Process one batch of due deliveries. Returns how many were attempted."""
    items = await asyncio.to_thread(_claim_due_deliveries)
    if not items:
        return 0
    await asyncio.gather(*(_send_one(item) for item in items))
    return len(items)


async def run_dispatcher_loop() -> None:
    """Background task: poll and deliver due notifications until cancelled."""
    while True:
        await asyncio.sleep(_POLL_INTERVAL_S)
        try:
            await dispatch_due()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("notification dispatcher tick failed")


# --------------------------------------------------------------------------- #
# Channel management (superuser API layer below uses these)
# --------------------------------------------------------------------------- #


def _secret_keys(target: NotificationTarget) -> set:
    return _SECRET_CONFIG_KEYS.get(target, set())


def serialize_channel(channel: NotificationChannel, *, mask: bool = True) -> Dict[str, Any]:
    """Project a channel to an API dict, masking secret config values.

    Secret values are replaced by a fixed placeholder and exposed as a
    ``has_<key>`` boolean so the UI can show "configured" without leaking the
    value. Non-secret config (chat_id, topic, server_url) is returned as-is.
    """
    try:
        config = json.loads(channel.config_json or "{}")
    except (TypeError, ValueError):
        config = {}
    try:
        events = json.loads(channel.events_json or "[]")
    except (TypeError, ValueError):
        events = []
    printer_ids = None
    if channel.printer_ids_json:
        try:
            printer_ids = json.loads(channel.printer_ids_json)
        except (TypeError, ValueError):
            printer_ids = None

    secrets = _secret_keys(channel.target)
    out_config: Dict[str, Any] = {}
    has: Dict[str, bool] = {}
    for key, value in config.items():
        if mask and key in secrets:
            has[f"has_{key}"] = bool(value)
            if value:
                out_config[key] = "********"
        else:
            out_config[key] = value
    return {
        "id": channel.id,
        "name": channel.name,
        "target": channel.target.value,
        "enabled": channel.enabled,
        "config": out_config,
        "config_flags": has,
        "events": events,
        "printer_ids": printer_ids,
        "last_status": channel.last_status,
        "last_error": channel.last_error,
        "last_delivered_at": (
            channel.last_delivered_at.isoformat() if channel.last_delivered_at else None
        ),
    }


def list_channels(session: Session) -> List[Dict[str, Any]]:
    channels = session.exec(
        select(NotificationChannel).order_by(NotificationChannel.id)  # type: ignore[arg-type]
    ).all()
    return [serialize_channel(c) for c in channels]


def get_channel(session: Session, channel_id: int) -> Optional[NotificationChannel]:
    return session.get(NotificationChannel, channel_id)


def create_channel(
    session: Session,
    *,
    name: str,
    target: NotificationTarget,
    config: Dict[str, Any],
    events: List[str],
    printer_ids: Optional[List[int]] = None,
    enabled: bool = True,
) -> NotificationChannel:
    channel = NotificationChannel(
        name=name,
        target=target,
        enabled=enabled,
        config_json=json.dumps(config or {}),
        events_json=json.dumps(_clean_events(events)),
        printer_ids_json=json.dumps(printer_ids) if printer_ids is not None else None,
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


def update_channel(
    session: Session,
    channel: NotificationChannel,
    *,
    name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    events: Optional[List[str]] = None,
    printer_ids: Optional[List[int]] = None,
    printer_ids_set: bool = False,
    enabled: Optional[bool] = None,
) -> NotificationChannel:
    """Patch a channel. Empty/omitted secret config values are preserved.

    ``printer_ids_set`` distinguishes "clear the scope" (explicit null) from
    "leave the scope unchanged" (field omitted), which a bare ``None`` cannot.
    """
    if name is not None:
        channel.name = name
    if enabled is not None:
        channel.enabled = enabled
    if events is not None:
        channel.events_json = json.dumps(_clean_events(events))
    if printer_ids_set:
        channel.printer_ids_json = (
            json.dumps(printer_ids) if printer_ids is not None else None
        )
    if config is not None:
        try:
            existing = json.loads(channel.config_json or "{}")
        except (TypeError, ValueError):
            existing = {}
        secrets = _secret_keys(channel.target)
        merged = dict(existing)
        for key, value in config.items():
            # A blank secret means "keep what's stored"; anything else overwrites.
            if key in secrets and (value is None or value == "" or value == "********"):
                continue
            merged[key] = value
        channel.config_json = json.dumps(merged)
    channel.updated_at = utcnow()
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


def delete_channel(session: Session, channel: NotificationChannel) -> None:
    session.delete(channel)
    session.commit()


def _clean_events(events: List[str]) -> List[str]:
    """Keep only valid, de-duplicated event-type values, preserving order."""
    valid = {e.value for e in NotificationEventType}
    seen: set = set()
    out: List[str] = []
    for e in events or []:
        if e in valid and e not in seen:
            seen.add(e)
            out.append(e)
    return out


def list_recent_deliveries(session: Session, *, limit: int = 50) -> List[Dict[str, Any]]:
    rows = session.exec(
        select(NotificationDelivery)
        .order_by(NotificationDelivery.created_at.desc())  # type: ignore[attr-defined]
        .limit(limit)
    ).all()
    out: List[Dict[str, Any]] = []
    for d in rows:
        out.append(
            {
                "id": d.id,
                "channel_id": d.channel_id,
                "event_type": d.event_type.value,
                "printer_id": d.printer_id,
                "status": d.status.value,
                "attempts": d.attempts,
                "last_error": d.last_error,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            }
        )
    return out


_SAMPLE_CONTEXT_EXTRA = {
    "job_id": 0,
    "filename": "sample.gcode",
    "model_name": "Sample model",
    "duration_s": 3661,
    "filament_used_g": 12.3,
    "error": None,
}


async def send_test(channel_id: int) -> Dict[str, Any]:
    """Render and send a synthetic event to one channel; return ``{ok, error}``.

    Used by the channel "Test" button. Sends immediately (no queue) so the UI
    gets instant feedback, and updates the channel's last-status like a real
    delivery would.
    """
    def _load() -> Optional[Dict[str, Any]]:
        with get_session_factory().session() as session:
            channel = session.get(NotificationChannel, channel_id)
            if channel is None:
                return None
            try:
                config = json.loads(channel.config_json or "{}")
            except (TypeError, ValueError):
                config = {}
            return {"target": channel.target, "config": config}

    loaded = await asyncio.to_thread(_load)
    if loaded is None:
        return {"ok": False, "error": "channel not found"}

    context = {
        "event": NotificationEventType.PRINT_COMPLETED.value,
        "printer_id": None,
        "printer_name": "Test printer",
        "timestamp": utcnow().isoformat().replace("+00:00", "Z"),
        **_SAMPLE_CONTEXT_EXTRA,
    }
    try:
        req = renderers.render(loaded["target"], context, loaded["config"])
    except renderers.RenderError as exc:
        await asyncio.to_thread(_record_channel_test, channel_id, False, str(exc))
        return {"ok": False, "error": str(exc)}
    try:
        client = get_http_client()
        resp = await client.request(
            req.method,
            req.url,
            headers=req.headers or None,
            json=req.json,
            content=req.data.encode("utf-8") if req.data is not None else None,
            timeout=_REQUEST_TIMEOUT_S,
        )
        if 200 <= resp.status_code < 300:
            await asyncio.to_thread(_record_channel_test, channel_id, True, None)
            return {"ok": True, "error": None}
        err = f"HTTP {resp.status_code}: {(resp.text or '')[:200]}"
        await asyncio.to_thread(_record_channel_test, channel_id, False, err)
        return {"ok": False, "error": err}
    except Exception as exc:  # noqa: BLE001 — network boundary
        await asyncio.to_thread(_record_channel_test, channel_id, False, str(exc))
        return {"ok": False, "error": str(exc)}


def _record_channel_test(channel_id: int, ok: bool, error: Optional[str]) -> None:
    now = utcnow()
    with get_session_factory().session() as session:
        channel = session.get(NotificationChannel, channel_id)
        if channel is None:
            return
        channel.last_status = "sent" if ok else "failed"
        channel.last_error = None if ok else (error or "")[:1024]
        if ok:
            channel.last_delivered_at = now
        channel.updated_at = now
        session.add(channel)
        session.commit()
