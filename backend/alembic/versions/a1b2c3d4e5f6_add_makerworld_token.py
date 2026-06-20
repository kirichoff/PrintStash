"""add makerworld session token to system_config

Revision ID: a1b2c3d4e5f6
Revises: d5e3a9c2f1b7
Create Date: 2026-06-20 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "d5e3a9c2f1b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column("makerworld_token", sa.String(length=4096), nullable=True),
    )
    op.add_column(
        "system_config",
        sa.Column("makerworld_token_updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("system_config", "makerworld_token_updated_at")
    op.drop_column("system_config", "makerworld_token")
