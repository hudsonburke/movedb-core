"""Tests for MoveDB catalog class."""

import polars as pl
import pytest
from pathlib import Path

from movedb import MoveDB


@pytest.fixture
def sample_data(tmp_path):
    """Create sample Parquet files for testing."""
    # Create subject directory
    subject_dir = tmp_path / "BAA01"
    subject_dir.mkdir()

    # Create markers
    markers_df = pl.DataFrame({
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
    markers_df.write_parquet(subject_dir / "markers.parquet")

    # Create events
    events_df = pl.DataFrame({
        "context": ["Left", "Right", "Left"],
        "label": ["Foot Strike", "Foot Off", "Foot Strike"],
        "time": [1.0, 1.5, 2.0],
        "trial_name": ["Walk01"] * 3,
        "subject_id": ["BAA01"] * 3,
        "session_id": ["baseline"] * 3,
    })
    events_df.write_parquet(subject_dir / "events.parquet")

    # Create sessions
    sessions_df = pl.DataFrame({
        "subject_id": ["BAA01"],
        "session_id": ["baseline"],
    })
    sessions_df.write_parquet(subject_dir / "sessions.parquet")

    return tmp_path


class TestMoveDB:
    def test_subjects(self, sample_data):
        """Test listing subjects."""
        db = MoveDB(sample_data)
        assert db.subjects() == ["BAA01"]

    def test_sessions(self, sample_data):
        """Test listing sessions for a subject."""
        db = MoveDB(sample_data)
        assert db.sessions("BAA01") == ["baseline"]

    def test_get_markers(self, sample_data):
        """Test loading markers."""
        db = MoveDB(sample_data)
        markers = db.get_markers("BAA01", "baseline")
        assert len(markers) == 3
        assert "marker_name" in markers.columns

    def test_get_markers_all_sessions(self, sample_data):
        """Test loading markers without session filter."""
        db = MoveDB(sample_data)
        markers = db.get_markers("BAA01")
        assert len(markers) == 3

    def test_get_events(self, sample_data):
        """Test loading events."""
        db = MoveDB(sample_data)
        events = db.get_events("BAA01", "baseline")
        assert len(events) == 3
        assert "context" in events.columns

    def test_get_sessions(self, sample_data):
        """Test loading sessions."""
        db = MoveDB(sample_data)
        sessions = db.get_sessions("BAA01")
        assert len(sessions) == 1
        assert sessions["subject_id"][0] == "BAA01"

    def test_query(self, sample_data):
        """Test SQL query."""
        db = MoveDB(sample_data)
        result = db.query("SELECT subject_id, session_id FROM BAA01_sessions")
        assert len(result) == 1
        assert result["subject_id"][0] == "BAA01"
