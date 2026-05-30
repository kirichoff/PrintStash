"""Unit tests for the G-code metadata parser."""

from __future__ import annotations

from pathlib import Path

from app.services.gcode_parser import parse, parse_duration


class TestParseDuration:
    def test_parse_hms(self) -> None:
        assert parse_duration("1h 23m 45s") == 5025

    def test_parse_days(self) -> None:
        assert parse_duration("2d 4h") == 187200

    def test_parse_seconds(self) -> None:
        assert parse_duration("90s") == 90

    def test_parse_plain_integer(self) -> None:
        assert parse_duration("3600") == 3600

    def test_parse_float(self) -> None:
        assert parse_duration("123.5") == 123

    def test_parse_empty(self) -> None:
        assert parse_duration("") is None

    def test_parse_nonsense(self) -> None:
        assert parse_duration("not a duration") is None


class TestParse:
    def test_parse_sample_gcode(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "sample.gcode"
        result = parse(fixture)
        assert result["slicer_name"] == "OrcaSlicer"
        assert result["slicer_version"] == "OrcaSlicer 1.9.0"
        assert result["printer_model"] == "Ender-3 V3 SE"
        assert result["nozzle_diameter_mm"] == 0.4
        assert result["layer_height_mm"] == 0.2
        assert result["infill_percent"] == 15.0
        assert result["estimated_time_s"] == 5025
        assert result["filament_weight_g"] == 12.5
        assert result["filament_length_mm"] == 4200.0
        assert result["filament_cost"] == 0.35
        assert result["material_type"] == "PLA"

    def test_parse_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        result = parse(tmp_path / "nonexistent.gcode")
        assert result["slicer_name"] is None
        assert result["estimated_time_s"] is None
