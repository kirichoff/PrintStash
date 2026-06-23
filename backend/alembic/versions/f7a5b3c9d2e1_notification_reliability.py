"""notification reliability: channel circuit-breaker counter

Revision ID: f7a5b3c9d2e1
Revises: e6f4a2b8c1d9
Create Date: 2026-06-21 12:00:00

Adds ``notification_channels.consecutive_failures`` for the auto-disable
circuit breaker. The new ``sending`` delivery status reuses the existing
``status`` text column, so no column change is needed for it.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f7a5b3c9d2e1"
down_revision = "e6f4a2b8c1d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_channels",
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_channels", "consecutive_failures")
