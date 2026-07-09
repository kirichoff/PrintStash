"""repair orphan rows before SQLite foreign keys are enforced

Revision ID: b2d8f6a1c94e
Revises: a1c7e4f9b23d
Create Date: 2026-07-09 13:30:00

SQLite only enforces foreign keys when ``PRAGMA foreign_keys=ON``, which this
release turns on for the first time. Until now nothing stopped a row from
outliving its parent — the hourly GC hard-deletes trashed users while
``models.created_by`` still points at them, for instance.

Existing orphans are tolerated by SQLite until something touches the row, so
they surface later as a mystery IntegrityError on an unrelated write. Repair
them here instead, driven by ``PRAGMA foreign_key_check`` so we fix exactly
what is actually broken:

  * dangling nullable reference  -> set NULL (loses an audit-trail name at worst)
  * dangling required reference  -> delete the row (it cannot be loaded anyway)

Postgres enforced these constraints all along, so it has nothing to repair.
"""

from __future__ import annotations

from alembic import op


revision = "b2d8f6a1c94e"
down_revision = "a1c7e4f9b23d"
branch_labels = None
depends_on = None


def _fk_column(conn, table: str, fk_id: int) -> tuple[str, bool]:
    """Return ``(column_name, nullable)`` for foreign key *fk_id* of *table*."""
    for row in conn.exec_driver_sql(f'PRAGMA foreign_key_list("{table}")'):
        if row[0] == fk_id:
            column = row[3]
            break
    else:
        raise RuntimeError(f"foreign key {fk_id} not found on {table}")

    for row in conn.exec_driver_sql(f'PRAGMA table_info("{table}")'):
        if row[1] == column:
            return column, not bool(row[3])
    raise RuntimeError(f"column {column} not found on {table}")


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "sqlite":
        return

    # foreign_key_check yields (table, rowid, parent_table, fk_id) per orphan.
    orphans = list(conn.exec_driver_sql("PRAGMA foreign_key_check"))
    if not orphans:
        return

    nulled = 0
    deleted = 0
    for table, rowid, _parent, fk_id in orphans:
        if rowid is None:  # WITHOUT ROWID table — nothing we can address
            continue
        column, nullable = _fk_column(conn, table, fk_id)
        if nullable:
            conn.exec_driver_sql(
                f'UPDATE "{table}" SET "{column}" = NULL WHERE rowid = ?', (rowid,)
            )
            nulled += 1
        else:
            conn.exec_driver_sql(f'DELETE FROM "{table}" WHERE rowid = ?', (rowid,))
            deleted += 1

    print(
        f"repaired foreign key orphans: {nulled} reference(s) cleared, "
        f"{deleted} unloadable row(s) removed"
    )

    remaining = list(conn.exec_driver_sql("PRAGMA foreign_key_check"))
    if remaining:
        raise RuntimeError(
            f"{len(remaining)} foreign key violation(s) remain after repair; "
            "refusing to enable enforcement on a dirty database"
        )


def downgrade() -> None:
    # Deleted rows and cleared references are not recoverable, and enforcement
    # simply stops when the pragma is off again.
    pass
