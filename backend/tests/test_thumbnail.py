"""Unit tests for embedded thumbnail extraction."""

from __future__ import annotations

from pathlib import Path

from app.services.thumbnail import extract


class TestExtract:
    def test_extract_sample_gcode(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "sample.gcode"
        result = extract(fixture)
        assert result is not None
        assert len(result) > 0
        assert result[:4] == b"\x89PNG"  # PNG magic bytes

    def test_extract_missing_file(self, tmp_path: Path) -> None:
        result = extract(tmp_path / "nonexistent.gcode")
        assert result is None

    def test_extract_no_thumbnail(self, tmp_path: Path) -> None:
        f = tmp_path / "no_thumb.gcode"
        f.write_text("G28\nG1 X10 Y10\nM84\n")
        result = extract(f)
        assert result is None
