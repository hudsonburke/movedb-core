"""Tests for patito schema definitions."""

import polars as pl
import pytest

from movedb.schemas import Markers, Forceplates, Events, Sessions


class TestMarkers:
    def test_valid_schema(self):
        """Test that Markers schema validates correct data."""
        df = pl.DataFrame({
            "frame": [0, 1, 2],
            "time": [0.0, 0.005, 0.01],
            "marker_name": ["LASI", "LASI", "LASI"],
            "x": [1.0, 1.1, 1.2],
            "y": [2.0, 2.1, 2.2],
            "z": [3.0, 3.1, 3.2],
            "trial_name": ["Walk01"] * 3,
            "subject_id": ["BAA01"] * 3,
            "session_id": ["baseline"] * 3,
        })
        markers = Markers.from_polars(df)
        assert markers is not None

    def test_from_parquet(self, tmp_path):
        """Test loading from Parquet file."""
        df = pl.DataFrame({
            "frame": [0, 1],
            "time": [0.0, 0.005],
            "marker_name": ["LASI", "LASI"],
            "x": [1.0, 1.1],
            "y": [2.0, 2.1],
            "z": [3.0, 3.1],
            "trial_name": ["Walk01"] * 2,
            "subject_id": ["BAA01"] * 2,
            "session_id": ["baseline"] * 2,
        })
        path = tmp_path / "markers.parquet"
        df.write_parquet(path)

        loaded = pl.read_parquet(path)
        markers = Markers.from_polars(loaded)
        assert markers is not None


class TestForceplates:
    def test_valid_schema(self):
        """Test that Forceplates schema validates correct data."""
        df = pl.DataFrame({
            "frame": [0, 1],
            "time": [0.0, 0.005],
            "fp_name": ["FP1", "FP1"],
            "variable": ["force", "force"],
            "axis": ["x", "x"],
            "value": [1.0, 2.0],
            "trial_name": ["Walk01"] * 2,
            "subject_id": ["BAA01"] * 2,
            "session_id": ["baseline"] * 2,
        })
        fps = Forceplates.from_polars(df)
        assert fps is not None


class TestEvents:
    def test_valid_schema(self):
        """Test that Events schema validates correct data."""
        df = pl.DataFrame({
            "context": ["Left", "Right"],
            "label": ["Foot Strike", "Foot Off"],
            "time": [1.0, 1.5],
            "trial_name": ["Walk01"] * 2,
            "subject_id": ["BAA01"] * 2,
            "session_id": ["baseline"] * 2,
        })
        events = Events.from_polars(df)
        assert events is not None


class TestSessions:
    def test_valid_schema(self):
        """Test that Sessions schema validates correct data."""
        df = pl.DataFrame({
            "subject_id": ["BAA01"],
            "session_id": ["baseline"],
            "Mass": [0.45],
            "RFemurLength": [32.0],
            "RTibiaLength": [39.0],
        })
        sessions = Sessions.from_polars(df)
        assert sessions is not None

    def test_optional_fields(self):
        """Test that optional fields can be None."""
        df = pl.DataFrame({
            "subject_id": ["BAA01"],
            "session_id": ["baseline"],
            "Mass": [0.45],
        })
        sessions = Sessions.from_polars(df)
        assert sessions is not None


class TestWithFields:
    def test_extend_schema(self):
        """Test extending schema with .with_fields()."""
        ForceplatesWithSide = Forceplates.with_fields(side=str)

        df = pl.DataFrame({
            "frame": [0, 1],
            "time": [0.0, 0.005],
            "fp_name": ["FP1", "FP1"],
            "variable": ["force", "force"],
            "axis": ["x", "x"],
            "value": [1.0, 2.0],
            "trial_name": ["Walk01"] * 2,
            "subject_id": ["BAA01"] * 2,
            "session_id": ["baseline"] * 2,
            "side": ["Left", "Left"],
        })
        fps = ForceplatesWithSide.from_polars(df)
        assert fps is not None
