"""spoolman integration: config switches + per-print spool link

Revision ID: a1c7e9b4d2f3
Revises: f7a5b3c9d2e1
Create Date: 2026-06-25 12:00:00

Adds the Spoolman master switch + connection config to ``system_config`` and a
soft spool reference (``spool_id``/``spool_name``) to ``print_jobs``. The
integration is OFF by default (``spoolman_enabled`` defaults false); write-back
defaults true but the API/UI flip it off when Moonraker's native hook is
detected.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1c7e9b4d2f3"
down_revision = "f7a5b3c9d2e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "spoolman_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "system_config",
        sa.Column("spoolman_base_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "system_config",
        sa.Column("spoolman_api_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "spoolman_write_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "print_jobs",
        sa.Column("spool_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "print_jobs",
        sa.Column("spool_name", sa.String(length=256), nullable=True),
    )
    op.create_index(
        "ix_print_jobs_spool_id", "print_jobs", ["spool_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_print_jobs_spool_id", table_name="print_jobs")
    op.drop_column("print_jobs", "spool_name")
    op.drop_column("print_jobs", "spool_id")
    op.drop_column("system_config", "spoolman_write_enabled")
    op.drop_column("system_config", "spoolman_api_key")
    op.drop_column("system_config", "spoolman_base_url")
    op.drop_column("system_config", "spoolman_enabled")
