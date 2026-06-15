"""add currency config

Revision ID: b7e3f1a2c9d4
Revises: a3f1c7d2e9b8
Create Date: 2026-06-15 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b7e3f1a2c9d4"
down_revision = "a3f1c7d2e9b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config", sa.Column("currency", sa.String(length=3), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("system_config", "currency")
