"""spoolman filament sync: link presets to Spoolman filaments

Revision ID: b2d8f1a6c3e4
Revises: a1c7e9b4d2f3
Create Date: 2026-06-25 13:00:00

Adds the link + physical-property columns that let a local FilamentProfile
mirror a Spoolman filament (the source of truth), and the spool's filament id
on print_jobs for exact per-print cost/grams.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b2d8f1a6c3e4"
down_revision = "a1c7e9b4d2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "filament_profiles",
        sa.Column("spoolman_filament_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "filament_profiles",
        sa.Column("density_g_cm3", sa.Float(), nullable=True),
    )
    op.add_column(
        "filament_profiles",
        sa.Column("diameter_mm", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_filament_profiles_spoolman_filament_id",
        "filament_profiles",
        ["spoolman_filament_id"],
        unique=False,
    )

    op.add_column(
        "print_jobs",
        sa.Column("spool_filament_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_print_jobs_spool_filament_id",
        "print_jobs",
        ["spool_filament_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_print_jobs_spool_filament_id", table_name="print_jobs")
    op.drop_column("print_jobs", "spool_filament_id")
    op.drop_index(
        "ix_filament_profiles_spoolman_filament_id", table_name="filament_profiles"
    )
    op.drop_column("filament_profiles", "diameter_mm")
    op.drop_column("filament_profiles", "density_g_cm3")
    op.drop_column("filament_profiles", "spoolman_filament_id")
