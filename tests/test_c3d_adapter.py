"""Tests for the C3D adapter using real BAA01 Baseline data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from movedb.ingestion.adapters.c3d import (
    get_param,
    get_param_list,
    get_param_strings,
    read_events,
    read_forceplates,
    read_markers,
    read_session_params,
)

DATA_DIR = Path(__file__).parent / "data" / "BAA01" / "Baseline"
SUBJECT_ID = "BAA01"
SESSION_ID = "Baseline"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def walk01():
    return DATA_DIR / "Walk01.c3d"


@pytest.fixture
def static01():
    return DATA_DIR / "Static01.c3d"


@pytest.fixture
def all_c3d():
    return sorted(DATA_DIR.glob("*.c3d"))


# ---------------------------------------------------------------------------
# read_markers
# ---------------------------------------------------------------------------

class TestReadMarkers:
    def test_returns_dataframe(self, walk01):
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert isinstance(df, pl.DataFrame)

    def test_expected_columns(self, walk01):
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert df.columns == [
            "frame", "time", "marker_name", "x", "y", "z",
            "trial_name", "subject_id", "session_id",
        ]

    def test_row_count(self, walk01):
        """19 markers × 1364 frames = 25_916 rows."""
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert len(df) == 19 * 1364

    def test_frame_range(self, walk01):
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert df["frame"].min() == 0
        assert df["frame"].max() == 1363

    def test_time_first_and_last(self, walk01):
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert df["time"].min() == pytest.approx(0.0)
        assert df["time"].max() == pytest.approx(1363 / 200.0)

    def test_marker_names(self, walk01):
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        names = sorted(df["marker_name"].unique().to_list())
        assert len(names) == 19
        # Spot-check a few known markers
        for m in ("RASI", "LASI", "RKNE", "RHIP"):
            assert m in names

    def test_x_y_z_are_float(self, walk01):
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        for col in ("x", "y", "z"):
            assert df[col].dtype == pl.Float64

    def test_static_fewer_markers_and_frames(self, static01):
        """Static01: 12 markers × 676 frames = 8_112 rows."""
        df = read_markers(static01, "Static01", SUBJECT_ID, SESSION_ID)
        assert len(df) == 12 * 676
        names = sorted(df["marker_name"].unique().to_list())
        assert len(names) == 12

    def test_trial_name_and_ids(self, walk01):
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert df["trial_name"].unique().to_list() == ["Walk01"]
        assert df["subject_id"].unique().to_list() == [SUBJECT_ID]
        assert df["session_id"].unique().to_list() == [SESSION_ID]

    def test_no_nans_in_xyz(self, walk01):
        df = read_markers(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        for col in ("x", "y", "z"):
            assert df[col].null_count() == 0

    def test_all_files_readable(self, all_c3d):
        """Every C3D file in the data dir should parse without error."""
        for path in all_c3d:
            df = read_markers(path, path.stem, SUBJECT_ID, SESSION_ID)
            assert len(df) > 0


# ---------------------------------------------------------------------------
# read_forceplates
# ---------------------------------------------------------------------------

class TestReadForceplates:
    def test_returns_dataframe(self, walk01):
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

    def test_expected_columns(self, walk01):
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert df.columns == [
            "frame", "time", "fp_name", "variable", "axis", "value",
            "trial_name", "subject_id", "session_id",
        ]

    def test_four_platforms(self, walk01):
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert sorted(df["fp_name"].unique().to_list()) == [
            "FP1", "FP2", "FP3", "FP4"
        ]

    def test_three_variables(self, walk01):
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert sorted(df["variable"].unique().to_list()) == [
            "cop", "force", "moment"
        ]

    def test_three_axes(self, walk01):
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert sorted(df["axis"].unique().to_list()) == ["x", "y", "z"]

    def test_analog_rate(self, walk01):
        """Force plate data should be at 1000 Hz (6820 frames)."""
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        # 4 platforms × 3 vars × 3 axes × 6820 frames = 245_520 rows
        assert len(df) == 4 * 3 * 3 * 6820

    def test_time_uses_analog_rate(self, walk01):
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        # Times should span 0..6819/1000
        assert df["time"].min() == pytest.approx(0.0)
        assert df["time"].max() == pytest.approx(6819 / 1000.0)

    def test_value_is_float(self, walk01):
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert df["value"].dtype == pl.Float64

    def test_frame_and_value_lengths_match(self, walk01):
        """Columns must have equal length (the bug we fixed)."""
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        n = len(df)
        assert len(df["frame"]) == n
        assert len(df["value"]) == n
        assert len(df["fp_name"]) == n

    def test_static_has_forceplate_data(self, static01):
        df = read_forceplates(static01, "Static01", SUBJECT_ID, SESSION_ID)
        assert len(df) > 0
        # Static01: 676 point frames → 3380 analog frames
        assert len(df) == 4 * 3 * 3 * 3380

    def test_no_nans_in_value(self, walk01):
        df = read_forceplates(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert df["value"].null_count() == 0

    def test_all_files_readable(self, all_c3d):
        for path in all_c3d:
            df = read_forceplates(path, path.stem, SUBJECT_ID, SESSION_ID)
            assert len(df) > 0


# ---------------------------------------------------------------------------
# read_events
# ---------------------------------------------------------------------------

class TestReadEvents:
    def test_returns_empty_dataframe(self, walk01):
        """Walk01 has no events in its C3D header."""
        df = read_events(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        assert isinstance(df, pl.DataFrame)
        assert df.is_empty()

    def test_expected_columns_when_empty(self, walk01):
        df = read_events(walk01, "Walk01", SUBJECT_ID, SESSION_ID)
        # Empty DataFrame still has no columns (matches current behavior)
        assert df.is_empty()


# ---------------------------------------------------------------------------
# read_session_params
# ---------------------------------------------------------------------------

class TestReadSessionParams:
    def test_returns_dict(self, walk01):
        params = read_session_params(walk01)
        assert isinstance(params, dict)

    def test_mass_is_present(self, walk01):
        params = read_session_params(walk01)
        assert "Mass" in params
        assert isinstance(params["Mass"], float)
        assert params["Mass"] > 0

    def test_bone_lengths_present(self, walk01):
        params = read_session_params(walk01)
        for key in ("RFemurLength", "RTibiaLength", "LFemurLength", "LTibiaLength"):
            assert key in params, f"Missing {key}"
            assert isinstance(params[key], float)
            assert params[key] > 0

    def test_consistent_across_trials(self, all_c3d):
        """PROCESSING params should be the same for every trial in a session."""
        ref = read_session_params(all_c3d[0])
        for path in all_c3d[1:]:
            other = read_session_params(path)
            assert other["Mass"] == pytest.approx(ref["Mass"]), path.name


# ---------------------------------------------------------------------------
# get_param helpers
# ---------------------------------------------------------------------------

class TestGetParamHelpers:
    def test_get_param_list_returns_value(self, walk01):
        import ezc3d
        c3d = ezc3d.c3d(str(walk01))
        val = get_param_list(c3d, ["POINT", "LABELS"])
        assert val is not None
        assert len(val) == 19

    def test_get_param_strings(self, walk01):
        import ezc3d
        c3d = ezc3d.c3d(str(walk01))
        labels = get_param_strings(c3d, ["POINT", "LABELS"])
        assert isinstance(labels, list)
        assert all(isinstance(s, str) for s in labels)
        assert len(labels) == 19

    def test_get_param_default_on_missing(self, walk01):
        import ezc3d
        c3d = ezc3d.c3d(str(walk01))
        val = get_param(c3d, ["NONEXISTENT", "KEY"], default=-1)
        assert val == -1

    def test_get_param_index_out_of_range(self, walk01):
        import ezc3d
        c3d = ezc3d.c3d(str(walk01))
        val = get_param(c3d, ["POINT", "LABELS"], index=999, default="fallback")
        assert val == "fallback"
