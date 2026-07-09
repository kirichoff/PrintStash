"""system_config: persist a generated JWT secret

Revision ID: a1c7e4f9b23d
Revises: f6b3d0a8c2e9
Create Date: 2026-07-09 13:00:00

Installs that never set VAULT_JWT_SECRET were signing tokens with the secret
published in .env.example and the compose defaults. On boot the app now
generates one and stores it here, so the replacement survives restarts. The
column stays NULL when the operator supplies the secret via the environment.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1c7e4f9b23d"
down_revision = "f6b3d0a8c2e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column("jwt_secret", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("system_config", "jwt_secret")
