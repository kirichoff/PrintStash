"""Unit coverage for ``notification_renderers`` — pure event -> request mapping.

These exercise the payload shape each target produces and the config-validation
boundary, with no network involved.
"""

from __future__ import annotations

import pytest

from app.db.models import NotificationTarget
from app.services import notification_renderers as r


def _ctx(**over):
    ctx = {
        "event": "print_completed",
        "printer_id": 3,
        "printer_name": "Ender 3",
        "filename": "benchy.gcode",
        "model_name": "3DBenchy",
        "job_id": 42,
        "duration_s": 3661,
        "filament_used_g": 12.34,
        "error": None,
        "timestamp": "2026-06-21T10:00:00Z",
    }
    ctx.update(over)
    return ctx


def test_webhook_wraps_full_context():
    req = r.render_webhook(_ctx(), {"url": "https://example.com/hook"})
    assert req.method == "POST"
    assert req.url == "https://example.com/hook"
    assert req.json["event"] == "print_completed"
    assert req.json["data"]["filename"] == "benchy.gcode"


def test_discord_builds_embed_with_color_and_fields():
    req = r.render_discord(_ctx(), {"url": "https://discord.com/api/webhooks/x/y"})
    embed = req.json["embeds"][0]
    assert embed["title"] == "Print completed — Ender 3"
    assert embed["color"] == 0x2ECC71  # green for completed
    names = {f["name"] for f in embed["fields"]}
    assert {"Printer", "Model", "File", "Duration", "Filament"} <= names
    assert embed["timestamp"] == "2026-06-21T10:00:00Z"


def test_discord_color_differs_for_failed():
    req = r.render_discord(_ctx(event="print_failed"), {"url": "https://d/x"})
    assert req.json["embeds"][0]["color"] == 0xE74C3C  # red


def test_telegram_targets_bot_api_with_markdown():
    req = r.render_telegram(_ctx(), {"bot_token": "123:ABC", "chat_id": "-100"})
    assert req.url == "https://api.telegram.org/bot123:ABC/sendMessage"
    assert req.json["chat_id"] == "-100"
    assert req.json["parse_mode"] == "Markdown"
    assert "*Print completed — Ender 3*" in req.json["text"]
    assert "File: benchy.gcode" in req.json["text"]


def test_ntfy_uses_default_server_headers_and_body():
    req = r.render_ntfy(_ctx(event="print_failed"), {"topic": "my3d"})
    assert req.url == "https://ntfy.sh/my3d"
    assert req.headers["Title"] == "Print failed — Ender 3"
    assert req.headers["Priority"] == "high"
    assert req.data and "Printer: Ender 3" in req.data
    assert "Authorization" not in req.headers


def test_ntfy_custom_server_strips_slash_and_adds_token():
    req = r.render_ntfy(
        _ctx(), {"topic": "t", "server_url": "https://push.me/", "token": "tk_abc"}
    )
    assert req.url == "https://push.me/t"
    assert req.headers["Authorization"] == "Bearer tk_abc"


def test_duration_formatting_hours_minutes():
    # 3661s -> "1h 1m"
    req = r.render_telegram(_ctx(), {"bot_token": "t", "chat_id": "c"})
    assert "Duration: 1h 1m" in req.json["text"]


def test_summary_skips_absent_optional_fields():
    lines = r.summary_lines(_ctx(model_name=None, filament_used_g=None, duration_s=None))
    joined = "\n".join(lines)
    assert "Model:" not in joined
    assert "Filament:" not in joined
    assert "Duration:" not in joined
    assert "File: benchy.gcode" in joined


@pytest.mark.parametrize("target", list(NotificationTarget))
def test_registry_covers_every_target(target):
    assert target in r.RENDERERS


@pytest.mark.parametrize(
    "target,config",
    [
        (NotificationTarget.WEBHOOK, {}),
        (NotificationTarget.DISCORD, {}),
        (NotificationTarget.TELEGRAM, {"bot_token": "t"}),  # missing chat_id
        (NotificationTarget.NTFY, {}),
    ],
)
def test_missing_required_config_raises(target, config):
    with pytest.raises(r.RenderError):
        r.render(target, _ctx(), config)
