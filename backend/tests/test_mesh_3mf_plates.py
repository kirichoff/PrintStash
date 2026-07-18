"""Feature #1 — parse a 3MF into per-plate object geometry without flattening.

``parse_3mf_plates`` preserves the plate→object grouping and each object's
bed placement, so the viewer can lay separated plates onto printer-sized beds
instead of concatenating every object into one blob.

Driven by the real 2-plate fixture (3DBenchy on plate 1, Torus on plate 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import mesh_processing

TESTDATA = Path(__file__).resolve().parents[2] / "testdata"
MULTIPLATE_3MF = TESTDATA / "multiplate_2plates_benchy_torus.3mf"
SPATULA_3MF = TESTDATA / "Spatula_Printables_IS.3mf"


def _requires(path: Path):
    return pytest.mark.skipif(not path.exists(), reason=f"missing real fixture {path}")


@_requires(MULTIPLATE_3MF)
def test_parse_3mf_two_plates_each_with_geometry() -> None:
    plates = mesh_processing.parse_3mf_plates(MULTIPLATE_3MF)
    assert len(plates) == 2, [p.index for p in plates]

    # Plates are 1-based and ordered.
    assert [p.index for p in plates] == [1, 2]

    for plate in plates:
        assert plate.objects, f"plate {plate.index} has no objects"
        for obj in plate.objects:
            # Each object carries a non-empty binary STL + a real bbox.
            assert obj.stl_bytes and len(obj.stl_bytes) > 84
            assert obj.bbox_mm[0] > 0 and obj.bbox_mm[1] > 0 and obj.bbox_mm[2] > 0


@_requires(MULTIPLATE_3MF)
def test_parse_3mf_plates_preserve_distinct_bed_placement() -> None:
    """The two objects sit far apart on the shared bed (tx 135.5 vs 459.5) — the
    parser must preserve that, not collapse them onto each other."""
    plates = mesh_processing.parse_3mf_plates(MULTIPLATE_3MF)
    origins_x = [obj.origin_mm[0] for p in plates for obj in p.objects]
    assert max(origins_x) - min(origins_x) > 100, origins_x


@_requires(SPATULA_3MF)
def test_parse_3mf_single_object_degrades_to_one_plate() -> None:
    """A generic 3MF with no Bambu/Orca plate config still yields one plate
    holding its object(s)."""
    plates = mesh_processing.parse_3mf_plates(SPATULA_3MF)
    assert len(plates) >= 1
    assert plates[0].objects
    assert plates[0].objects[0].stl_bytes
