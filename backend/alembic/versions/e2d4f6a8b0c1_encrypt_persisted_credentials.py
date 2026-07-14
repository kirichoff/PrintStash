"""encrypt persisted integration credentials

Revision ID: e2d4f6a8b0c1
Revises: f1c2d3e4a5b6
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.secrets import decrypt_secret, encrypt_secret

revision: str = "e2d4f6a8b0c1"
down_revision: str | None = "f1c2d3e4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = {
    "printers": {
        "api_key": 128,
        "bambu_access_code": 128,
        "prusalink_password": 255,
        "prusalink_api_key": 255,
        "elegoo_centauri_access_code": 255,
        "octoprint_api_key": 255,
    },
    "system_config": {
        "jwt_secret": 128,
        "s3_access_key": 256,
        "s3_secret_key": 512,
        "backup_s3_access_key": 256,
        "backup_s3_secret_key": 512,
        "spoolman_api_key": 512,
        "makerworld_token": 4096,
    },
}


def _transform(transform) -> None:
    connection = op.get_bind()
    for table, columns in _COLUMNS.items():
        rows = connection.execute(
            sa.text(f"SELECT id, {', '.join(columns)} FROM {table}")
        ).mappings()
        for row in rows:
            updates = {
                column: transform(row[column])
                for column in columns
                if row[column] is not None
            }
            if updates:
                assignments = ", ".join(f"{key} = :{key}" for key in updates)
                connection.execute(
                    sa.text(f"UPDATE {table} SET {assignments} WHERE id = :row_id"),
                    {**updates, "row_id": row["id"]},
                )

    rows = connection.execute(
        sa.text("SELECT id, config_json FROM notification_channels")
    ).mappings()
    for row in rows:
        connection.execute(
            sa.text(
                "UPDATE notification_channels SET config_json = :value WHERE id = :row_id"
            ),
            {"value": transform(row["config_json"]), "row_id": row["id"]},
        )


def upgrade() -> None:
    for table, columns in _COLUMNS.items():
        with op.batch_alter_table(table) as batch_op:
            for column, length in columns.items():
                batch_op.alter_column(
                    column,
                    existing_type=sa.String(length=length),
                    type_=sa.Text(),
                    existing_nullable=True,
                )
    _transform(encrypt_secret)


def downgrade() -> None:
    _transform(decrypt_secret)
    for table, columns in _COLUMNS.items():
        with op.batch_alter_table(table) as batch_op:
            for column, length in columns.items():
                batch_op.alter_column(
                    column,
                    existing_type=sa.Text(),
                    type_=sa.String(length=length),
                    existing_nullable=True,
                )
