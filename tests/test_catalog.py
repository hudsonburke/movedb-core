"""Tests for MoveDB catalog class."""

import polars as pl
import pytest
from pathlib import Path

from movedb import MoveDB


@pytest.fixture
def sample_data(tmp_path):
    """Create sample Parquet files for testing."""
    subject_dir = tmp_path / "BAA01"
    subject_dir.mkdir()

    # Points (renamed from markers)
    points_df = pl.DataFrame({
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
    })
    points_df.write_parquet(subject_dir / "points.parquet")

    # Parameters
    params_df = pl.DataFrame({
        "trial_name": ["Walk01"],
        "subject_id": ["BAA01"],
        "session_id": ["baseline"],
        "Mass": [0.45],
    })
    params_df.write_parquet(subject_dir / "parameters.parquet")

    # Events
    events_df = pl.DataFrame({
        "context": ["Left", "Right", "Left"],
        "label": ["Foot Strike", "Foot Off", "Foot Strike"],
        "time": [1.0, 1.5, 2.0],
        "trial_name": ["Walk01"] * 3,
        "subject_id": ["BAA01"] * 3,
        "session_id": ["baseline"] * 3,
    })
    events_df.write_parquet(subject_dir / "events.parquet")

    return tmp_path


class TestMoveDB:
    def test_subjects(self, sample_data):
        db = MoveDB(sample_data)
        assert db.subjects() == ["BAA01"]

    def test_sessions(self, sample_data):
        db = MoveDB(sample_data)
        assert db.sessions("BAA01") == ["baseline"]

    def test_sessions_all_subjects(self, sample_data):
        db = MoveDB(sample_data)
        assert db.sessions() == ["baseline"]

    def test_trials(self, sample_data):
        db = MoveDB(sample_data)
        assert db.trials("BAA01") == ["Walk01"]

    def test_get_points(self, sample_data):
        db = MoveDB(sample_data)
        df = db.get_points("BAA01")
        assert len(df) == 3
        assert "marker_name" in df.columns
        assert "residual" in df.columns

    def test_get_points_filtered(self, sample_data):
        db = MoveDB(sample_data)
        df = db.get_points("BAA01", session="baseline")
        assert len(df) == 3

    def test_get_points_column_pruning(self, sample_data):
        db = MoveDB(sample_data)
        df = db.get_points("BAA01", columns=["frame", "x", "y"])
        assert df.columns == ["frame", "x", "y"]

    def test_get_parameters(self, sample_data):
        db = MoveDB(sample_data)
        df = db.get_parameters("BAA01")
        assert len(df) == 1
        assert "Mass" in df.columns

    def test_get_events(self, sample_data):
        db = MoveDB(sample_data)
        df = db.get_events("BAA01")
        assert len(df) == 3
        assert "context" in df.columns

    def test_query(self, sample_data):
        db = MoveDB(sample_data)
        path = str(sample_data / "BAA01" / "parameters.parquet")
        result = db.query(f"SELECT subject_id, Mass FROM '{path}' WHERE subject_id = 'BAA01'")
        assert len(result) == 1
        assert result["subject_id"][0] == "BAA01"

    def test_query_across_files(self, sample_data):
        """Query joins across different parquet files."""
        db = MoveDB(sample_data)
        points_path = str(sample_data / "BAA01" / "points.parquet")
        params_path = str(sample_data / "BAA01" / "parameters.parquet")
        sql = (
            f"SELECT p.trial_name, COUNT(f.frame) as n_points "
            f"FROM '{points_path}' f "
            f"JOIN '{params_path}' p ON f.trial_name = p.trial_name "
            f"WHERE f.subject_id = 'BAA01' "
            f"GROUP BY p.trial_name"
        )
        # nosemgrep: test fixture — SQL is a hardcoded literal
        result = db.query(sql)  # noqa: S608
        assert len(result) == 1
        assert result["n_points"][0] == 3

    def test_schema(self, sample_data):
        db = MoveDB(sample_data)
        df = db.schema("points")
        assert "column_name" in df.columns
        assert "column_type" in df.columns

    def test_empty_data_dir(self, tmp_path):
        db = MoveDB(tmp_path)
        assert db.subjects() == []
        assert db.sessions() == []
