"""scrub secrets already captured in audit_log diffs

Revision ID: 9a1e5c7d3f02
Revises: 175be54ef975
Create Date: 2026-07-09 16:00:00

The ORM ``after_flush`` audit listener wrote unredacted before/after values
for every changed column into ``audit_logs.diff_json``, including printer API
keys, runtime-config secrets (S3, Spoolman, MakerWorld, the JWT secret), and
password/token hashes — readable by any admin via ``GET /admin/audit``. The
listener itself is fixed (``app.services.audit._diff_for_obj`` now redacts
these fields going forward); this scrubs rows written before that fix.

Blunt on purpose: rewriting each historical diff to keep its non-secret keys
would mean re-parsing arbitrary JSON per resource type for diffs nobody
reads. Affected resource types are wiped to an empty diff instead.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9a1e5c7d3f02"
down_revision = "175be54ef975"
branch_labels = None
depends_on = None

_AFFECTED_RESOURCE_TYPES = (
    "printers",
    "system_config",
    "users",
    "api_keys",
    "notification_channels",
)


def upgrade() -> None:
    conn = op.get_bind()
    placeholders = ", ".join(f":rt{i}" for i in range(len(_AFFECTED_RESOURCE_TYPES)))
    params = {f"rt{i}": rt for i, rt in enumerate(_AFFECTED_RESOURCE_TYPES)}
    conn.execute(
        sa.text(
            f"UPDATE audit_logs SET diff_json = '{{}}' "
            f"WHERE resource_type IN ({placeholders})"
        ),
        params,
    )


def downgrade() -> None:
    # Scrubbed data is not recoverable.
    pass
