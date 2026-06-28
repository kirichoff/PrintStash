"""collections: add markdown readme landing page

Revision ID: d4f1b8c2e6a7
Revises: c3e9a7d1f5b2
Create Date: 2026-06-28 12:00:00

Adds ``collections.readme`` — a markdown "landing page" per collection holding
descriptions, print notes, and (self-hosted) image references. Nullable; empty
collections render no readme.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d4f1b8c2e6a7"
down_revision = "c3e9a7d1f5b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collections", sa.Column("readme", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("collections", "readme")
