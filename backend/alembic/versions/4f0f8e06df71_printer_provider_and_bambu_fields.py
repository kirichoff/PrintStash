"""printer provider and bambu fields

Revision ID: 4f0f8e06df71
Revises: 69b6a6d8a1d1
Create Date: 2026-05-30 16:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "4f0f8e06df71"
down_revision = "69b6a6d8a1d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "printers",
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="moonraker"),
    )
    op.create_index("ix_printers_provider", "printers", ["provider"], unique=False)
    op.add_column("printers", sa.Column("bambu_host", sa.String(length=255), nullable=True))
    op.add_column(
        "printers", sa.Column("bambu_serial", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "printers", sa.Column("bambu_access_code", sa.String(length=128), nullable=True)
    )

    with op.batch_alter_table("printers") as batch_op:
        batch_op.alter_column("moonraker_url", existing_type=sa.String(length=512), nullable=False, server_default="")


def downgrade() -> None:
    with op.batch_alter_table("printers") as batch_op:
        batch_op.alter_column("moonraker_url", existing_type=sa.String(length=512), nullable=False, server_default=None)

    op.drop_column("printers", "bambu_access_code")
    op.drop_column("printers", "bambu_serial")
    op.drop_column("printers", "bambu_host")
    op.drop_index("ix_printers_provider", table_name="printers")
    op.drop_column("printers", "provider")
