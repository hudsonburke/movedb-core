from __future__ import annotations

import numpy as np
import polars as pl

from movedb.adapters.polars import analogs_to_polars, forceplates_to_polars, markers_to_polars
from movedb.core import AnalogData, ForceplateData, MarkerData
from movedb.storage.schemas import MarkerWideValue
from movedb.storage.validation import (
    _create_dynamic_wide_model,
    validate_analogs_wide,
    validate_forceplates_wide,
    validate_markers_wide,
)


def test_dynamic_wide_models_are_cached() -> None:
    first = _create_dynamic_wide_model("MarkerWideRow", MarkerWideValue, ("A", "B"), require_identity=False)
    second = _create_dynamic_wide_model("MarkerWideRow", MarkerWideValue, ("A", "B"), require_identity=False)
    assert first is second


def test_validate_markers_wide_allows_diagonal_concat_missing_marker_columns() -> None:
    trial_a = MarkerData(
        rate=100.0,
        first_frame=1,
        names=["A", "B"],
        units="mm",
        data=np.array([[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]]),
    )
    trial_b = MarkerData(
        rate=100.0,
        first_frame=2,
        names=["A", "C"],
        units="mm",
        data=np.array([[[7.0, 8.0, 9.0], [10.0, 11.0, 12.0]]]),
    )

    df = pl.concat(
        [
            markers_to_polars(trial_a, format="wide", trial_name="TrialA"),
            markers_to_polars(trial_b, format="wide", trial_name="TrialB"),
        ],
        how="diagonal",
    )
    metadata = trial_a.metadata().model_copy(update={"names": ["A", "B", "C"]})

    validated = validate_markers_wide(df, metadata)
    assert validated.height == df.height
    assert {"A", "B", "C"}.issubset(set(validated.columns))
    assert {"subject_id", "session_id"}.issubset(set(validated.columns))


def test_validate_analogs_wide_casts_integer_signal_columns() -> None:
    analog_data = AnalogData(
        rate=1000.0,
        first_frame=1,
        names=["EMG1", "EMG2"],
        units=["V", "V"],
        data=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64),
    )

    df = analogs_to_polars(analog_data, format="wide", trial_name="Walk01").with_columns(
        pl.col("EMG1").cast(pl.Int64),
        pl.col("EMG2").cast(pl.Int64),
    )
    validated = validate_analogs_wide(df, analog_data.metadata())

    assert validated.schema["EMG1"] == pl.Float64
    assert validated.schema["EMG2"] == pl.Float64


def test_validate_forceplates_wide_adds_missing_free_moment() -> None:
    forceplate_data = ForceplateData(
        rate=1000.0,
        first_frame=1,
        names=["FP1"],
        units_force=["N"],
        units_moment=["Nmm"],
        units_position=["mm"],
        origins=np.zeros((3, 1)),
        corners=np.zeros((4, 1, 3)),
        cal_matrices=np.zeros((6, 1, 6)),
        forces=np.ones((2, 1, 3)),
        moments=np.ones((2, 1, 3)) * 2,
        cop=np.ones((2, 1, 3)) * 3,
    )

    df = forceplates_to_polars(forceplate_data, format="wide", trial_name="Walk01")
    validated = validate_forceplates_wide(df, forceplate_data.metadata())

    field_names = {field.name for field in validated.schema["FP1"].fields}
    assert "free_moment" in field_names
