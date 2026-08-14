"""Tests for the C3D adapter using real BAA01 Baseline data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from movedb.ingestion.adapters.c3d import (
    get_param,
    get_param_list,
    get_param_strings,
    read_analogs,
    read_events,
    read_forceplate_geometry,
    read_forceplates,
    read_parameters,
    read_points,
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
# read_points
# ---------------------------------------------------------------------------


class TestReadPoints:
    def test_returns_dataframe(self, walk01):
        df = read_points(walk01, "Walk01")
        assert isinstance(df, pl.DataFrame)

    def test_expected_columns(self, walk01):
        df = read_points(walk01, "Walk01")
        assert "frame" in df.columns
        assert "time" in df.columns
        assert "marker_name" in df.columns
        assert "x" in df.columns
        assert "y" in df.columns
        assert "z" in df.columns
        assert "residual" in df.columns
        assert "camera_mask" in df.columns
        assert "trial_name" in df.columns

    def test_row_count(self, walk01):
        """19 markers × 1364 frames = 25_916 rows."""
        df = read_points(walk01, "Walk01")
        assert len(df) == 19 * 1364

    def test_frame_range(self, walk01):
        df = read_points(walk01, "Walk01")
        assert df["frame"].min() == 0
        assert df["frame"].max() == 1363

    def test_time_first_and_last(self, walk01):
        df = read_points(walk01, "Walk01")
        assert df["time"].min() == pytest.approx(0.0)
        assert df["time"].max() == pytest.approx(1363 / 200.0)

    def test_marker_names(self, walk01):
        df = read_points(walk01, "Walk01")
        names = sorted(df["marker_name"].unique().to_list())
        assert len(names) == 19
        for m in ("RASI", "LASI", "RKNE", "RHIP"):
            assert m in names

    def test_x_y_z_are_float(self, walk01):
        df = read_points(walk01, "Walk01")
        for col in ("x", "y", "z"):
            assert df[col].dtype == pl.Float64

    def test_residual_is_float(self, walk01):
        df = read_points(walk01, "Walk01")
        assert df["residual"].dtype == pl.Float64

    def test_camera_mask_is_list(self, walk01):
        df = read_points(walk01, "Walk01")
        # camera_mask should be a list column
        assert df["camera_mask"].dtype == pl.List(pl.Int64)

    def test_camera_mask_length(self, walk01):
        """Each camera mask should have 7 elements (one per camera)."""
        df = read_points(walk01, "Walk01")
        first_mask = df["camera_mask"][0]
        assert len(first_mask) == 7

    def test_static_fewer_markers_and_frames(self, static01):
        """Static01: 12 markers × 676 frames = 8_112 rows."""
        df = read_points(static01, "Static01")
        assert len(df) == 12 * 676
        names = sorted(df["marker_name"].unique().to_list())
        assert len(names) == 12

    def test_trial_name(self, walk01):
        df = read_points(walk01, "Walk01")
        assert df["trial_name"].unique().to_list() == ["Walk01"]

    def test_no_nans_in_xyz(self, walk01):
        df = read_points(walk01, "Walk01")
        for col in ("x", "y", "z"):
            assert df[col].null_count() == 0

    def test_backward_compat_alias(self, walk01):
        """read_markers should be an alias for read_points."""
        from movedb.ingestion.adapters.c3d import read_markers
        assert read_markers is read_points

    def test_all_files_readable(self, all_c3d):
        """Every C3D file in the data dir should parse without error."""
        for path in all_c3d:
            df = read_points(path, path.stem)
            assert len(df) > 0


# ---------------------------------------------------------------------------
# read_forceplates
# ---------------------------------------------------------------------------


class TestReadForceplates:
    def test_returns_dataframe(self, walk01):
        df = read_forceplates(walk01, "Walk01")
        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

    def test_expected_columns(self, walk01):
        df = read_forceplates(walk01, "Walk01")
        assert df.columns == [
            "frame", "time", "fp_name", "variable", "axis", "value", "trial_name",
        ]

    def test_four_platforms(self, walk01):
        df = read_forceplates(walk01, "Walk01")
        assert sorted(df["fp_name"].unique().to_list()) == ["FP1", "FP2", "FP3", "FP4"]

    def test_three_variables(self, walk01):
        df = read_forceplates(walk01, "Walk01")
        assert sorted(df["variable"].unique().to_list()) == ["cop", "force", "moment"]

    def test_three_axes(self, walk01):
        df = read_forceplates(walk01, "Walk01")
        assert sorted(df["axis"].unique().to_list()) == ["x", "y", "z"]

    def test_analog_rate(self, walk01):
        """Force plate data should be at 1000 Hz (6820 frames)."""
        df = read_forceplates(walk01, "Walk01")
        assert len(df) == 4 * 3 * 3 * 6820

    def test_time_uses_analog_rate(self, walk01):
        df = read_forceplates(walk01, "Walk01")
        assert df["time"].min() == pytest.approx(0.0)
        assert df["time"].max() == pytest.approx(6819 / 1000.0)

    def test_no_nans_in_value(self, walk01):
        df = read_forceplates(walk01, "Walk01")
        assert df["value"].null_count() == 0

    def test_all_files_readable(self, all_c3d):
        for path in all_c3d:
            df = read_forceplates(path, path.stem)
            assert len(df) > 0


# ---------------------------------------------------------------------------
# read_forceplate_geometry
# ---------------------------------------------------------------------------


class TestReadForceplateGeometry:
    def test_returns_dataframe(self, walk01):
        df = read_forceplate_geometry(walk01, "Walk01")
        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

    def test_expected_columns(self, walk01):
        df = read_forceplate_geometry(walk01, "Walk01")
        assert "fp_name" in df.columns
        assert "origin" in df.columns
        assert "corners" in df.columns
        assert "cal_matrix" in df.columns
        assert "trial_name" in df.columns

    def test_four_platforms(self, walk01):
        df = read_forceplate_geometry(walk01, "Walk01")
        assert len(df) == 4
        assert sorted(df["fp_name"].unique().to_list()) == ["FP1", "FP2", "FP3", "FP4"]

    def test_origin_is_3d(self, walk01):
        """Origin should be a list of 3 floats."""
        df = read_forceplate_geometry(walk01, "Walk01")
        for origin in df["origin"]:
            assert len(origin) == 3

    def test_corners_shape(self, walk01):
        """Corners should be a flattened 3×4 array (12 floats)."""
        df = read_forceplate_geometry(walk01, "Walk01")
        for corners in df["corners"]:
            assert len(corners) == 12

    def test_cal_matrix_shape(self, walk01):
        """Cal matrix should be empty or 36 floats."""
        df = read_forceplate_geometry(walk01, "Walk01")
        for cal in df["cal_matrix"]:
            assert len(cal) == 0 or len(cal) == 36

    def test_all_files_readable(self, all_c3d):
        for path in all_c3d:
            df = read_forceplate_geometry(path, path.stem)
            assert len(df) > 0


# ---------------------------------------------------------------------------
# read_analogs
# ---------------------------------------------------------------------------


class TestReadAnalogs:
    def test_returns_dataframe(self, walk01):
        df = read_analogs(walk01, "Walk01")
        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

    def test_expected_columns(self, walk01):
        df = read_analogs(walk01, "Walk01")
        assert "frame" in df.columns
        assert "time" in df.columns
        assert "channel_name" in df.columns
        assert "value" in df.columns
        assert "unit" in df.columns
        assert "trial_name" in df.columns

    def test_channel_count(self, walk01):
        """Should have 30 analog channels."""
        df = read_analogs(walk01, "Walk01")
        assert df["channel_name"].n_unique() == 30

    def test_analog_rate(self, walk01):
        """Analog data should be at 1000 Hz."""
        df = read_analogs(walk01, "Walk01")
        assert df["time"].min() == pytest.approx(0.0)
        assert df["time"].max() == pytest.approx(6819 / 1000.0)

    def test_units_present(self, walk01):
        df = read_analogs(walk01, "Walk01")
        units = df["unit"].unique().to_list()
        assert "N" in units  # Force units
        assert "Nmm" in units  # Moment units

    def test_all_files_readable(self, all_c3d):
        for path in all_c3d:
            df = read_analogs(path, path.stem)
            assert len(df) > 0


# ---------------------------------------------------------------------------
# read_events
# ---------------------------------------------------------------------------


class TestReadEvents:
    def test_returns_empty_dataframe(self, walk01):
        """Walk01 has no events in its C3D header."""
        df = read_events(walk01, "Walk01")
        assert isinstance(df, pl.DataFrame)
        assert df.is_empty()


# ---------------------------------------------------------------------------
# read_parameters
# ---------------------------------------------------------------------------


class TestReadParameters:
    def test_returns_dict(self, walk01):
        params = read_parameters(walk01)
        assert isinstance(params, dict)

    def test_mass_is_present(self, walk01):
        params = read_parameters(walk01)
        assert "Mass" in params
        assert isinstance(params["Mass"], float)
        assert params["Mass"] > 0

    def test_bone_lengths_present(self, walk01):
        params = read_parameters(walk01)
        for key in ("RFemurLength", "RTibiaLength", "LFemurLength", "LTibiaLength"):
            assert key in params, f"Missing {key}"
            assert isinstance(params[key], float)
            assert params[key] > 0

    def test_trial_params_present(self, walk01):
        """TRIAL group params should be included."""
        params = read_parameters(walk01)
        # TRIAL.CAMERA_RATE or similar should be present
        assert any(k.startswith("CAMERA") or k.startswith("ACTUAL") for k in params)

    def test_consistent_across_trials(self, all_c3d):
        """PROCESSING params should be the same for every trial in a session."""
        ref = read_parameters(all_c3d[0])
        for path in all_c3d[1:]:
            other = read_parameters(path)
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


# ---------------------------------------------------------------------------
# Schema attachment (patito models)
# ---------------------------------------------------------------------------


class TestSchemaAttachment:
    """Verify patito models are attached for downstream type checking."""

    def test_points_model_attached(self, walk01):
        import patito as pt
        df = read_points(walk01, "Walk01")
        assert issubclass(type(df), pt.DataFrame)

    def test_forceplates_model_attached(self, walk01):
        import patito as pt
        df = read_forceplates(walk01, "Walk01")
        assert issubclass(type(df), pt.DataFrame)

    def test_events_model_attached(self, walk01):
        import patito as pt
        df = read_events(walk01, "Walk01")
        # Empty DF — no model attached (pl.DataFrame returned early)
        assert isinstance(df, pl.DataFrame)


# ---------------------------------------------------------------------------
# Parameters schema extension with PROCESSING parameters
# ---------------------------------------------------------------------------

_SESSION_BASE_FIELDS: dict[str, Any] = {
    "Mass": (float, ...),
    "Length": (float, ...),
    "RFemurLength": (float, ...),
    "RTibiaLength": (float, ...),
    "RFootLength": (float, ...),
    "RThighMass": (float, ...),
    "RThighCOM_X": (float, ...),
    "RThighCOM_Y": (float, ...),
    "RThighCOM_Z": (float, ...),
    "RThighMOI_X": (float, ...),
    "RThighMOI_Y": (float, ...),
    "RThighMOI_Z": (float, ...),
    "RShankMass": (float, ...),
    "RShankCOM_X": (float, ...),
    "RShankCOM_Y": (float, ...),
    "RShankCOM_Z": (float, ...),
    "RShankMOI_X": (float, ...),
    "RShankMOI_Y": (float, ...),
    "RShankMOI_Z": (float, ...),
    "RFootMass": (float, ...),
    "RFootCOM_X": (float, ...),
    "RFootCOM_Y": (float, ...),
    "RFootCOM_Z": (float, ...),
    "RFootMOI_X": (float, ...),
    "RFootMOI_Y": (float, ...),
    "RFootMOI_Z": (float, ...),
    "LFemurLength": (float, ...),
    "LTibiaLength": (float, ...),
    "LFootLength": (float, ...),
    "LThighMass": (float, ...),
    "LThighCOM_X": (float, ...),
    "LThighCOM_Y": (float, ...),
    "LThighCOM_Z": (float, ...),
    "LThighMOI_X": (float, ...),
    "LThighMOI_Y": (float, ...),
    "LThighMOI_Z": (float, ...),
    "LShankMass": (float, ...),
    "LShankCOM_X": (float, ...),
    "LShankCOM_Y": (float, ...),
    "LShankCOM_Z": (float, ...),
    "LShankMOI_X": (float, ...),
    "LShankMOI_Y": (float, ...),
    "LShankMOI_Z": (float, ...),
    "LFootMass": (float, ...),
    "LFootCOM_X": (float, ...),
    "LFootCOM_Y": (float, ...),
    "LFootCOM_Z": (float, ...),
    "LFootMOI_X": (float, ...),
    "LFootMOI_Y": (float, ...),
    "LFootMOI_Z": (float, ...),
}


class TestParametersSchemaExtension:
    """Test extending Parameters schema with PROCESSING params from real C3D files."""

    def test_schema_extends_with_fields(self):
        from movedb.schemas.models import Parameters
        Extended = Parameters.with_fields(**_SESSION_BASE_FIELDS)
        assert "Mass" in Extended.model_fields
        assert "RFemurLength" in Extended.model_fields
        assert "trial_name" in Extended.model_fields

    def test_extended_schema_validates_dataframe(self, walk01):
        from movedb.schemas.models import Parameters
        params = read_parameters(walk01)
        params["trial_name"] = "Walk01"
        params["subject_id"] = SUBJECT_ID
        params["session_id"] = SESSION_ID
        Extended = Parameters.with_fields(**_SESSION_BASE_FIELDS)
        df = pl.DataFrame([params])
        Extended.validate(df, allow_superfluous_columns=True)

    def test_mass_value(self, walk01):
        from movedb.schemas.models import Parameters
        params = read_parameters(walk01)
        params["trial_name"] = "Walk01"
        params["subject_id"] = SUBJECT_ID
        params["session_id"] = SESSION_ID
        Extended = Parameters.with_fields(**_SESSION_BASE_FIELDS)
        df = pl.DataFrame([params])
        Extended.validate(df, allow_superfluous_columns=True)

    def test_bone_lengths(self, walk01):
        from movedb.schemas.models import Parameters
        params = read_parameters(walk01)
        params["trial_name"] = "Walk01"
        params["subject_id"] = SUBJECT_ID
        params["session_id"] = SESSION_ID
        Extended = Parameters.with_fields(**_SESSION_BASE_FIELDS)
        df = pl.DataFrame([params])
        Extended.validate(df, allow_superfluous_columns=True)
        assert df["RFemurLength"][0] == pytest.approx(31.5)
        assert df["RTibiaLength"][0] == pytest.approx(41.0)
        assert df["LFemurLength"][0] == pytest.approx(32.0)
        assert df["LTibiaLength"][0] == pytest.approx(41.0)

    def test_all_files_produce_valid_params(self, all_c3d):
        from movedb.schemas.models import Parameters
        Extended = Parameters.with_fields(**_SESSION_BASE_FIELDS)
        for path in all_c3d:
            params = read_parameters(path)
            params["trial_name"] = path.stem
            params["subject_id"] = SUBJECT_ID
            params["session_id"] = SESSION_ID
            df = pl.DataFrame([params])
            Extended.validate(df, allow_superfluous_columns=True)

    def test_rejects_unexpected_columns(self, walk01):
        from movedb.schemas.models import Parameters
        params = read_parameters(walk01)
        params["trial_name"] = "Walk01"
        params["subject_id"] = SUBJECT_ID
        params["session_id"] = SESSION_ID
        params["UnexpectedParam"] = 999.0
        Extended = Parameters.with_fields(**_SESSION_BASE_FIELDS)
        df = pl.DataFrame([params])
        with pytest.raises(Exception, match="Superfluous"):
            Extended.validate(df)

    def test_rejects_missing_required_columns(self, walk01):
        from movedb.schemas.models import Parameters
        Extended = Parameters.with_fields(**_SESSION_BASE_FIELDS)
        params = read_parameters(walk01)
        df = pl.DataFrame([params])
        with pytest.raises(Exception):
            Extended.validate(df)

    def test_with_all_params(self, walk01):
        from movedb.schemas.models import Parameters
        params = read_parameters(walk01)
        params["trial_name"] = "Walk01"
        params["subject_id"] = SUBJECT_ID
        params["session_id"] = SESSION_ID
        all_fields = {
            k: (type(v), ...)
            for k, v in params.items()
            if k not in ("trial_name", "subject_id", "session_id")
        }
        Extended = Parameters.with_fields(**all_fields)
        df = pl.DataFrame([params])
        Extended.validate(df)
