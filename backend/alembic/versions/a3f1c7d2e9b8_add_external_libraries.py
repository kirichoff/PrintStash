"""add external libraries (NAS folder mirroring)

Revision ID: a3f1c7d2e9b8
Revises: ab4f6d9e2c31
Create Date: 2026-06-15 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a3f1c7d2e9b8"
down_revision = "ab4f6d9e2c31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_libraries",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("root_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "scan_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
        sa.Column(
            "collection_mode",
            sa.String(length=16),
            nullable=False,
            server_default="mirror",
        ),
        sa.Column(
            "target_collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id"),
            nullable=True,
        ),
        sa.Column("last_scanned_at", sa.DateTime(), nullable=True),
        sa.Column("last_scan_status", sa.String(length=16), nullable=True),
        sa.Column("last_scan_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_external_libraries_enabled", "external_libraries", ["enabled"]
    )

    op.add_column(
        "files",
        sa.Column(
            "is_external",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "files",
        sa.Column("external_library_id", sa.Integer(), nullable=True),
    )
    op.add_column("files", sa.Column("source_mtime", sa.Float(), nullable=True))
    op.create_index("ix_files_is_external", "files", ["is_external"])
    op.create_index(
        "ix_files_external_library_id", "files", ["external_library_id"]
    )

    op.add_column(
        "system_config",
        sa.Column(
            "external_libraries_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "external_libraries_enabled")
    op.drop_index("ix_files_external_library_id", table_name="files")
    op.drop_index("ix_files_is_external", table_name="files")
    op.drop_column("files", "source_mtime")
    op.drop_column("files", "external_library_id")
    op.drop_column("files", "is_external")
    op.drop_index("ix_external_libraries_enabled", table_name="external_libraries")
    op.drop_table("external_libraries")
