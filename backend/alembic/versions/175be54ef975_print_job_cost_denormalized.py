"""denormalise per-job filament cost onto print_jobs

Revision ID: 175be54ef975
Revises: b2d8f6a1c94e
Create Date: 2026-07-09 15:00:00

``print_statistics`` used to hydrate every completed PrintJob + Metadata +
Model + Collection row and re-match a filament profile per row on every
dashboard load. This adds ``print_jobs.cost`` and
``print_jobs.filament_g_effective``, backfilled here, so the aggregate can be
a plain ``SUM()``.

The backfill replays the cost resolution that
``app.services.model_views.filament_cost_for_job`` performs (spool-linked
profile first, then a fuzzy metadata match, then the slicer's own estimate)
frozen as of this migration — a migration must stay stable even if that
service logic changes later, so this does not import it.

Behavior change (call out in the changelog): going forward, a completed
print's cost is fixed at completion time. Editing a filament profile's price
no longer changes the cost of print jobs that already finished.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "175be54ef975"
down_revision = "b2d8f6a1c94e"
branch_labels = None
depends_on = None


def _normalise(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().lower()
    return stripped or None


def _matching_profile(profiles: list[dict], material_type, material_brand):
    candidates = [_normalise(material_brand), _normalise(material_type)]
    for candidate in candidates:
        if candidate is None:
            continue
        for profile in profiles:
            if _normalise(profile["name"]) == candidate:
                return profile

    norm_type = _normalise(material_type)
    norm_brand = _normalise(material_brand)
    if norm_type is None:
        return None
    for profile in profiles:
        if _normalise(profile["material_type"]) != norm_type:
            continue
        if norm_brand is not None:
            if _normalise(profile["material_brand"]) == norm_brand:
                return profile
        elif profile["material_brand"] is None:
            return profile
    return None


def _cost_for_grams(profiles, material_type, material_brand, grams):
    if grams is None:
        return None
    profile = _matching_profile(profiles, material_type, material_brand)
    if profile is None or profile["cost_per_kg"] is None:
        return None
    return round(grams * profile["cost_per_kg"] / 1000, 4)


def _resolve(job, md, profiles):
    """Return (grams_effective, cost) for one print_jobs row, frozen logic."""
    spool_filament_id = job["spool_filament_id"]
    measured_grams = job["filament_used_g"]

    if measured_grams is not None:
        grams = measured_grams
    elif md is not None:
        grams = md["filament_weight_g"]
    else:
        grams = None

    material_type = md["material_type"] if md is not None else None
    material_brand = md["material_brand"] if md is not None else None

    cost = None
    if grams is not None and spool_filament_id is not None:
        for profile in profiles:
            if (
                profile["spoolman_filament_id"] == spool_filament_id
                and profile["cost_per_kg"] is not None
            ):
                cost = round(grams * profile["cost_per_kg"] / 1000, 4)
                break
    if cost is None:
        cost = _cost_for_grams(profiles, material_type, material_brand, grams)
    if cost is None and measured_grams is None and md is not None:
        # Slicer's own cost estimate, used when no profile matches at all.
        cost = md["filament_cost"]

    return grams, cost


def upgrade() -> None:
    with op.batch_alter_table("print_jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cost", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("filament_g_effective", sa.Float(), nullable=True)
        )

    conn = op.get_bind()

    profiles = [
        dict(row._mapping)
        for row in conn.execute(
            sa.text(
                "SELECT id, name, material_type, material_brand, cost_per_kg, "
                "spoolman_filament_id FROM filament_profiles"
            )
        )
    ]
    metadata_by_file = {
        row._mapping["file_id"]: dict(row._mapping)
        for row in conn.execute(
            sa.text(
                "SELECT file_id, material_type, material_brand, filament_weight_g, "
                "filament_cost FROM metadata"
            )
        )
    }
    jobs = [
        dict(row._mapping)
        for row in conn.execute(
            sa.text(
                "SELECT id, file_id, filament_used_g, spool_filament_id FROM print_jobs"
            )
        )
    ]

    update_stmt = sa.text(
        "UPDATE print_jobs SET filament_g_effective = :grams, cost = :cost "
        "WHERE id = :id"
    )
    for job in jobs:
        md = metadata_by_file.get(job["file_id"])
        grams, cost = _resolve(job, md, profiles)
        if grams is None and cost is None:
            continue
        conn.execute(update_stmt, {"grams": grams, "cost": cost, "id": job["id"]})


def downgrade() -> None:
    with op.batch_alter_table("print_jobs", schema=None) as batch_op:
        batch_op.drop_column("filament_g_effective")
        batch_op.drop_column("cost")
