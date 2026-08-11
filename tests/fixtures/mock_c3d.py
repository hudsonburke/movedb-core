"""Synthetic test data for C3D ingestion tests.

Creates mock C3D-like structures that mimic real data patterns:
- Different marker sets across trials (causes width mismatch)
- PROCESSING parameters for scaling
- Long-format marker DataFrames with varying columns
"""

import numpy as np
import polars as pl
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class MockMarkerData:
    """Mock marker data mimicking C3D structure."""
    names: list[str]
    data: np.ndarray  # (n_frames, n_markers, 3)
    rate: float = 200.0
    first_frame: int = 0
    residuals: np.ndarray | None = None


@dataclass
class MockC3d:
    """Mock C3D file structure."""
    markers: MockMarkerData
    processing: dict = field(default_factory=dict)
    trial_name: str = "test_trial"


# Standard marker sets for different trial types
STANDARD_MARKERS = [
    "TAIL", "SPL6", "LASI", "RASI",
    "LHIP", "LKNE", "LANK", "LTOE",
    "RHIP", "RKNE", "RANK", "RTOE",
]

EXTENDED_MARKERS = STANDARD_MARKERS + [
    "LFOR", "RFOR", "LHEE", "RHEE",
    "LMKM", "RMKM", "LMKL", "RMKL",
]

MINIMAL_MARKERS = ["LASI", "RASI", "LKNE", "RKNE", "LANK", "RANK"]


def create_mock_markers(
    marker_names: list[str],
    n_frames: int = 100,
    rate: float = 200.0,
    first_frame: int = 0,
    fill_value: float = 1.0,
) -> MockMarkerData:
    """Create mock marker data with specified markers."""
    n_markers = len(marker_names)
    # Create realistic-ish marker positions
    data = np.random.rand(n_frames, n_markers, 3) * 0.1 + fill_value
    return MockMarkerData(
        names=marker_names,
        data=data,
        rate=rate,
        first_frame=first_frame,
    )


def create_mock_processing(
    mass: float = 0.45,
    rfemur: float = 32.0,
    rtibia: float = 39.0,
    lfemur: float = 31.5,
    ltibia: float = 38.5,
) -> dict:
    """Create mock PROCESSING parameters."""
    return {
        "Mass": {"value": [mass]},
        "RFemurLength": {"value": [rfemur]},
        "RTibiaLength": {"value": [rtibia]},
        "LFemurLength": {"value": [lfemur]},
        "LTibiaLength": {"value": [ltibia]},
        "RFootLength": {"value": [25.0]},
        "LFootLength": {"value": [24.5]},
    }


def create_mock_c3d(
    trial_name: str = "test_trial",
    marker_names: list[str] | None = None,
    n_frames: int = 100,
    processing: dict | None = None,
) -> MockC3d:
    """Create a mock C3D file."""
    if marker_names is None:
        marker_names = STANDARD_MARKERS.copy()

    markers = create_mock_markers(marker_names, n_frames)
    proc = processing or create_mock_processing()

    return MockC3d(
        markers=markers,
        processing=proc,
        trial_name=trial_name,
    )


def markers_to_long_df(
    c3d: MockC3d,
    subject_id: str = "TEST01",
    session: str = "baseline",
) -> pl.DataFrame:
    """Convert mock C3D to long-format markers DataFrame (mimics movedb-core output)."""
    data = c3d.markers.data
    n_frames, n_markers, _ = data.shape

    time = np.arange(n_frames) / c3d.markers.rate
    frames = np.arange(c3d.markers.first_frame, c3d.markers.first_frame + n_frames)

    time_repeated = np.repeat(time, n_markers)
    frame_repeated = np.repeat(frames, n_markers)
    marker_names_repeated = np.tile(c3d.markers.names, n_frames)
    xyz_data = data.reshape(-1, 3)

    df = pl.DataFrame({
        "time": time_repeated,
        "frame": frame_repeated,
        "marker_name": marker_names_repeated,
        "x": xyz_data[:, 0],
        "y": xyz_data[:, 1],
        "z": xyz_data[:, 2],
        "trial_name": [c3d.trial_name] * len(time_repeated),
        "subject_id": [subject_id] * len(time_repeated),
        "session_id": [session] * len(time_repeated),
    })

    return df


def create_session_data(
    subject_id: str = "TEST01",
    session: str = "baseline",
    trials: list[dict] | None = None,
) -> list[pl.DataFrame]:
    """Create a list of marker DataFrames simulating a session with multiple trials.

    Each trial dict should have:
    - trial_name: str
    - marker_names: list[str] (optional, defaults to STANDARD_MARKERS)
    - n_frames: int (optional, defaults to 100)
    """
    if trials is None:
        trials = [
            {"trial_name": "Walk01", "marker_names": STANDARD_MARKERS, "n_frames": 100},
            {"trial_name": "Walk02", "marker_names": EXTENDED_MARKERS, "n_frames": 150},
            {"trial_name": "Static01", "marker_names": STANDARD_MARKERS, "n_frames": 50},
        ]

    dfs = []
    for trial in trials:
        c3d = create_mock_c3d(
            trial_name=trial["trial_name"],
            marker_names=trial.get("marker_names", STANDARD_MARKERS),
            n_frames=trial.get("n_frames", 100),
        )
        df = markers_to_long_df(c3d, subject_id, session)
        dfs.append(df)

    return dfs


# Sample data for regression tests
SAMPLE_SESSIONS = {
    "BAA01": {
        "baseline": {
            "trials": [
                {"trial_name": "Walk01", "marker_names": STANDARD_MARKERS, "n_frames": 100},
                {"trial_name": "Walk02", "marker_names": EXTENDED_MARKERS, "n_frames": 150},
                {"trial_name": "Static01", "marker_names": STANDARD_MARKERS, "n_frames": 50},
            ],
            "processing": create_mock_processing(mass=0.42, rfemur=31.5, rtibia=38.2),
        },
        "week12": {
            "trials": [
                {"trial_name": "Walk01", "marker_names": EXTENDED_MARKERS, "n_frames": 120},
                {"trial_name": "Walk02", "marker_names": STANDARD_MARKERS, "n_frames": 100},
            ],
            "processing": create_mock_processing(mass=0.48, rfemur=33.1, rtibia=40.5),
        },
    },
    "BAA02": {
        "baseline": {
            "trials": [
                {"trial_name": "Walk01", "marker_names": MINIMAL_MARKERS, "n_frames": 80},
                {"trial_name": "Static01", "marker_names": MINIMAL_MARKERS, "n_frames": 50},
            ],
            "processing": create_mock_processing(mass=0.38, rfemur=30.2, rtibia=37.1),
        },
    },
}
