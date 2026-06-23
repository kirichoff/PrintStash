"""add notification channels, deliveries, and master switch

Revision ID: e6f4a2b8c1d9
Revises: a1b2c3d4e5f6
Create Date: 2026-06-21 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e6f4a2b8c1d9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("target", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("events_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("printer_ids_json", sa.Text(), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("last_delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_channels_target", "notification_channels", ["target"]
    )
    op.create_index(
        "ix_notification_channels_enabled", "notification_channels", ["enabled"]
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("printer_id", sa.Integer(), nullable=True),
        sa.Column("print_job_id", sa.Integer(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["notification_channels.id"]),
        sa.ForeignKeyConstraint(["printer_id"], ["printers.id"]),
        sa.ForeignKeyConstraint(["print_job_id"], ["print_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_deliveries_channel_id",
        "notification_deliveries",
        ["channel_id"],
    )
    op.create_index(
        "ix_notification_deliveries_status", "notification_deliveries", ["status"]
    )
    op.create_index(
        "ix_notification_deliveries_next_retry_at",
        "notification_deliveries",
        ["next_retry_at"],
    )
    op.create_index(
        "ix_notification_deliveries_event_type",
        "notification_deliveries",
        ["event_type"],
    )
    op.create_index(
        "ix_notification_deliveries_printer_id",
        "notification_deliveries",
        ["printer_id"],
    )
    op.create_index(
        "ix_notification_deliveries_print_job_id",
        "notification_deliveries",
        ["print_job_id"],
    )
    op.create_index(
        "ix_notification_deliveries_created_at",
        "notification_deliveries",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_index(
        "ix_notification_channels_enabled", table_name="notification_channels"
    )
    op.drop_index(
        "ix_notification_channels_target", table_name="notification_channels"
    )
    op.drop_table("notification_channels")
    op.drop_column("system_config", "notifications_enabled")
