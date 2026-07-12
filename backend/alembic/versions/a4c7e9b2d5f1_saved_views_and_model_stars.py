"""saved views and model stars

Revision ID: a4c7e9b2d5f1
Revises: e2b6c9a4f7d3
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4c7e9b2d5f1"
down_revision: str | None = "e2b6c9a4f7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_saved_views_user_name"),
    )
    op.create_index("ix_saved_views_user_id", "saved_views", ["user_id"])
    op.create_table(
        "model_stars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "model_id", name="uq_model_stars_user_model"),
    )
    op.create_index("ix_model_stars_model_id", "model_stars", ["model_id"])
    op.create_index("ix_model_stars_user_id", "model_stars", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_model_stars_user_id", table_name="model_stars")
    op.drop_index("ix_model_stars_model_id", table_name="model_stars")
    op.drop_table("model_stars")
    op.drop_index("ix_saved_views_user_id", table_name="saved_views")
    op.drop_table("saved_views")
