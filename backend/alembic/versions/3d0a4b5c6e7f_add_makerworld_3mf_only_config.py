"""add makerworld_3mf_only config

Revision ID: 3d0a4b5c6e7f
Revises: f7a5b3c9d2e1
Create Date: 2026-07-17 04:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3d0a4b5c6e7f"
down_revision: Union[str, None] = "f7a5b3c9d2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "makerworld_3mf_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "makerworld_3mf_only")
