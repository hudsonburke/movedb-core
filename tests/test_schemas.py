"""Tests for patito schema definitions."""

import polars as pl
import pytest

from movedb.schemas import (
    TrialMetadata,
    Points,
    Forceplates,
    ForceplateGeometry,
    Analogs,
    Events,
    Parameters,
)


class TestPoints:
    def test_valid_schema(self):
        """Test that Points schema validates correct data."""
        df = pl.DataFrame(
            {
                "frame": [0, 1, 2],
                "time": [0.0, 0.005, 0.01],
                "marker_name": ["LASI", "LASI", "LASI"],
                "x": [1.0, 1.1, 1.2],
                "y": [2.0, 2.1, 2.2],
                "z": [3.0, 3.1, 3.2],
                "residual": [0.1, 0.2, 0.3],
                "camera_mask": [[1, 1, 1, 1, 1, 1, 1]] * 3,
                "trial_name": ["Walk01"] * 3,
                "subject_id": ["BAA01"] * 3,
                "session_id": ["baseline"] * 3,
            }
        )
        Points.validate(df)

    def test_from_parquet(self, tmp_path):
        """Test loading from Parquet file."""
        df = pl.DataFrame(
            {
                "frame": [0, 1],
                "time": [0.0, 0.005],
                "marker_name": ["LASI", "LASI"],
                "x": [1.0, 1.1],
                "y": [2.0, 2.1],
                "z": [3.0, 3.1],
                "residual": [0.1, 0.2],
                "camera_mask": [[1, 1, 1, 1, 1, 1, 1]] * 2,
                "trial_name": ["Walk01"] * 2,
                "subject_id": ["BAA01"] * 2,
                "session_id": ["baseline"] * 2,
            }
        )
        path = tmp_path / "points.parquet"
        df.write_parquet(path)

        loaded = pl.read_parquet(path)
        Points.validate(loaded)


class TestForceplates:
    def test_valid_schema(self):
        """Test that Forceplates schema validates correct data."""
        df = pl.DataFrame(
            {
                "frame": [0, 1],
                "time": [0.0, 0.005],
                "fp_name": ["FP1", "FP1"],
                "variable": ["force", "force"],
                "axis": ["x", "x"],
                "value": [1.0, 2.0],
                "trial_name": ["Walk01"] * 2,
                "subject_id": ["BAA01"] * 2,
                "session_id": ["baseline"] * 2,
            }
        )
        Forceplates.validate(df)


class TestForceplateGeometry:
    def test_valid_schema(self):
        """Test that ForceplateGeometry schema validates correct data."""
        df = pl.DataFrame(
            {
                "fp_name": ["FP1"],
                "origin": [[0.0, 0.0, 0.0]],
                "corners": [[0.0] * 12],
                "cal_matrix": [[0.0] * 36],
                "trial_name": ["Walk01"],
                "subject_id": ["BAA01"],
                "session_id": ["baseline"],
            }
        )
        ForceplateGeometry.validate(df)


class TestAnalogs:
    def test_valid_schema(self):
        """Test that Analogs schema validates correct data."""
        df = pl.DataFrame(
            {
                "frame": [0, 1],
                "time": [0.0, 0.001],
                "channel_name": ["Force.Fx1", "Force.Fx1"],
                "value": [10.0, 20.0],
                "unit": ["N", "N"],
                "trial_name": ["Walk01"] * 2,
                "subject_id": ["BAA01"] * 2,
                "session_id": ["baseline"] * 2,
            }
        )
        Analogs.validate(df)


class TestEvents:
    def test_valid_schema(self):
        """Test that Events schema validates correct data."""
        df = pl.DataFrame(
            {
                "context": ["Left", "Right"],
                "label": ["Foot Strike", "Foot Off"],
                "time": [1.0, 1.5],
                "trial_name": ["Walk01"] * 2,
                "subject_id": ["BAA01"] * 2,
                "session_id": ["baseline"] * 2,
            }
        )
        Events.validate(df)


class TestTrialMetadata:
    def test_valid_schema(self):
        """Test that TrialMetadata schema validates correct data."""
        df = pl.DataFrame(
            {
                "trial_name": ["Walk01"],
                "subject_id": ["BAA01"],
                "session_id": ["baseline"],
            }
        )
        TrialMetadata.validate(df)

    def test_inherited_by_points(self):
        """Test that Points inherits from TrialMetadata."""
        assert issubclass(Points, TrialMetadata)

    def test_inherited_by_forceplates(self):
        """Test that Forceplates inherits from TrialMetadata."""
        assert issubclass(Forceplates, TrialMetadata)

    def test_inherited_by_events(self):
        """Test that Events inherits from TrialMetadata."""
        assert issubclass(Events, TrialMetadata)

    def test_inherited_by_parameters(self):
        """Test that Parameters inherits from TrialMetadata."""
        assert issubclass(Parameters, TrialMetadata)


class TestParameters:
    def test_valid_schema(self):
        """Test that Parameters schema validates correct data."""
        df = pl.DataFrame(
            {
                "trial_name": ["Walk01"],
                "subject_id": ["BAA01"],
                "session_id": ["baseline"],
            }
        )
        Parameters.validate(df)

    def test_extend_schema(self):
        """Test extending Parameters with .with_fields()."""
        RatParameters = Parameters.with_fields(Mass=(float, ...), RFemurLength=(float, ...))
        df = pl.DataFrame(
            {
                "trial_name": ["Walk01"],
                "subject_id": ["BAA01"],
                "session_id": ["baseline"],
                "Mass": [0.45],
                "RFemurLength": [32.0],
            }
        )
        RatParameters.validate(df)


class TestWithFields:
    def test_extend_schema(self):
        """Test extending schema with .with_fields()."""
        ForceplatesWithSide = Forceplates.with_fields(side=(str, ...))

        df = pl.DataFrame(
            {
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
            }
        )

        ForceplatesWithSide.validate(df)
