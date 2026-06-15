"""external library cron schedule + watch mode

Revision ID: c4d2f8a1b6e3
Revises: b7e3f1a2c9d4
Create Date: 2026-06-15 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c4d2f8a1b6e3"
down_revision = "b7e3f1a2c9d4"
branch_labels = None
depends_on = None


def _interval_to_cron(minutes: int) -> str:
    """Approximate a fixed minute interval as a cron expression."""
    if minutes <= 0:
        return ""  # manual only
    if minutes < 60:
        return f"*/{minutes} * * * *"
    if minutes == 60:
        return "0 * * * *"
    if minutes % 1440 == 0:
        return f"0 0 */{minutes // 1440} * *"
    if minutes % 60 == 0 and (minutes // 60) < 24:
        return f"0 */{minutes // 60} * * *"
    return "0 * * * *"  # fall back to hourly


def upgrade() -> None:
    op.add_column(
        "external_libraries",
        sa.Column(
            "scan_schedule",
            sa.String(length=128),
            nullable=False,
            server_default="0 * * * *",
        ),
    )
    op.add_column(
        "external_libraries",
        sa.Column(
            "watch_mode",
            sa.String(length=16),
            nullable=False,
            # SQLAlchemy persists Python enums by *member name*, so the default
            # must be "AUTO" (not the "auto" value) to round-trip on read.
            server_default="AUTO",
        ),
    )
    op.add_column(
        "external_libraries",
        sa.Column("fs_kind", sa.String(length=16), nullable=True),
    )

    # Backfill scan_schedule from the legacy scan_interval_minutes.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, scan_interval_minutes FROM external_libraries")
    ).fetchall()
    for row_id, minutes in rows:
        cron = _interval_to_cron(int(minutes or 60))
        bind.execute(
            sa.text(
                "UPDATE external_libraries SET scan_schedule = :cron WHERE id = :id"
            ),
            {"cron": cron, "id": row_id},
        )


def downgrade() -> None:
    op.drop_column("external_libraries", "fs_kind")
    op.drop_column("external_libraries", "watch_mode")
    op.drop_column("external_libraries", "scan_schedule")
