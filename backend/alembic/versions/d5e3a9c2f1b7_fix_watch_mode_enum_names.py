"""repair external_libraries.watch_mode to store enum names

Revision c4d2f8a1b6e3 wrote the column default as the lowercase enum *value*
("auto"), but SQLAlchemy persists Python enums by member *name* ("AUTO"). Rows
that picked up that default fail to read back ("'auto' is not among the defined
enum values"), 500-ing the libraries listing. Normalise any lowercase values to
their enum names.

Revision ID: d5e3a9c2f1b7
Revises: c4d2f8a1b6e3
Create Date: 2026-06-15 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d5e3a9c2f1b7"
down_revision = "c4d2f8a1b6e3"
branch_labels = None
depends_on = None

_FIXUP = {"auto": "AUTO", "events": "EVENTS", "off": "OFF"}


def upgrade() -> None:
    bind = op.get_bind()
    for value, name in _FIXUP.items():
        bind.execute(
            sa.text(
                "UPDATE external_libraries SET watch_mode = :name "
                "WHERE watch_mode = :value"
            ),
            {"name": name, "value": value},
        )


def downgrade() -> None:
    # Reverting to the broken lowercase values would re-break reads; no-op.
    pass
