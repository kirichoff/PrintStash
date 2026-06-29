"""documents: standalone document items (markdown / PDF) in collections

Revision ID: f6b3d0a8c2e9
Revises: d4f1b8c2e6a7
Create Date: 2026-06-28 14:00:00

A Document is a first-class library item shown alongside models. Markdown docs
keep editable content in ``body``; binary docs (PDF/other) store a ``filename``
and a blob under the storage backend's document_file_key.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f6b3d0a8c2e9"
down_revision = "d4f1b8c2e6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_documents_name", "documents", ["name"])
    op.create_index("ix_documents_kind", "documents", ["kind"])
    op.create_index("ix_documents_collection_id", "documents", ["collection_id"])
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])
    op.create_index("ix_documents_updated_at", "documents", ["updated_at"])


def downgrade() -> None:
    op.drop_table("documents")
