"""spoolman: add write-back force override for the native-hook guard

Revision ID: c3e9a7d1f5b2
Revises: b2d8f1a6c3e4
Create Date: 2026-06-26 16:40:00

Adds ``system_config.spoolman_write_force``. The consumption write-back now
checks Spoolman's active spool at write time and skips the decrement when
Moonraker's native hook is already counting that spool. This flag lets an
operator who has disabled Moonraker's own decrement force the write-back on
regardless. Off by default so the guard protects users who never open the
Spoolman settings card.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c3e9a7d1f5b2"
down_revision = "b2d8f1a6c3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "spoolman_write_force",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "spoolman_write_force")
