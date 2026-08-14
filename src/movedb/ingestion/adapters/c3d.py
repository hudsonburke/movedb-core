"""C3D file adapter — reads C3D files and produces DataFrames.

This module reads C3D files using ezc3d and produces Polars DataFrames
that can be validated with patito schemas and written to Parquet.
"""

from __future__ import annotations

import logging
from pathlib import Path

import ezc3d
import numpy as np
import polars as pl

logger = logging.getLogger(__name__)


def get_param_list(
    c3d: ezc3d.c3d, keys: list[str], default: list | None = None
) -> list | np.ndarray:
    """Navigate nested C3D parameters and return the value list."""
    param: dict = c3d.parameters
    for key in keys:
        param = param.get(key, {})
    value = param.get("value")
    if value is None:
        return default if default is not None else []
    return value


def get_param_strings(
    c3d: ezc3d.c3d, keys: list[str], default: list[str] | None = None
) -> list[str]:
    """Get parameter value as list of strings."""
    value = get_param_list(c3d, keys)
    if isinstance(value, np.ndarray):
        return value.astype(str).ravel().tolist()
    if value is None or len(value) == 0:
        return default if default is not None else []
    return [str(v) for v in value]


def get_param(c3d: ezc3d.c3d, keys: list[str], index: int = 0, default=None):
    """Get a single indexed value from a C3D parameter list."""
    param_list = get_param_list(c3d, keys)
    if not hasattr(param_list, "__len__") or len(param_list) == 0:
        return default
    if index < 0 or index >= len(param_list):
        return default
    value = param_list[index]
    return value if value is not None else default


def read_markers(c3d_path: str | Path, trial_name: str, subject_id: str, session_id: str) -> pl.DataFrame:
    """Read markers from C3D file and return DataFrame.
    
    Returns long-format DataFrame with columns:
    frame, time, marker_name, x, y, z, trial_name, subject_id, session_id
    """
    c3d = ezc3d.c3d(str(c3d_path))
    
    point_rate = get_param(c3d, ["POINT", "RATE"], default=100.0)
    n_frames = c3d["header"]["points"]["last_frame"] - c3d["header"]["points"]["first_frame"] + 1
    labels = get_param_strings(c3d, ["POINT", "LABELS"])
    n_markers = len(labels)
    
    # Extract marker positions (3, n_markers, n_frames)
    data = c3d["data"]["points"]
    
    # Create arrays for each column — derive times from frames to avoid duplicate arange
    frames = np.repeat(np.arange(n_frames), n_markers)
    times = frames / point_rate
    marker_names = np.tile(labels, n_frames)
    x = data[0, :, :].T.flatten()
    y = data[1, :, :].T.flatten()
    z = data[2, :, :].T.flatten()
    
    return pl.DataFrame({
        "frame": frames.astype(int),
        "time": times,
        "marker_name": marker_names,
        "x": x.astype(float),
        "y": y.astype(float),
        "z": z.astype(float),
        "trial_name": trial_name,
        "subject_id": subject_id,
        "session_id": session_id,
    })


def read_forceplates(c3d_path: str | Path, trial_name: str, subject_id: str, session_id: str) -> pl.DataFrame:
    """Read force plate data from C3D file and return DataFrame.
    
    Returns long-format DataFrame with columns:
    frame, time, fp_name, variable, axis, value, trial_name, subject_id, session_id
    """
    c3d = ezc3d.c3d(str(c3d_path), extract_forceplat_data=True)
    
    # Force plate data is sampled at the analog rate (often 1000 Hz),
    # which can differ from the marker point rate (e.g. 200 Hz).
    analog_rate = get_param(c3d, ["ANALOG", "RATE"], default=1000.0)

    platforms = c3d["data"].get("platform", [])
    if not platforms:
        return pl.DataFrame()

    var_names = ("force", "moment", "cop")
    var_keys = ("force", "moment", "center_of_pressure")
    axis_names = ("x", "y", "z")
    n_vars = len(var_names)
    n_axes = len(axis_names)

    frames_parts: list[np.ndarray] = []
    times_parts: list[np.ndarray] = []
    fp_names_parts: list[np.ndarray] = []
    variables_parts: list[np.ndarray] = []
    axes_parts: list[np.ndarray] = []
    values_parts: list[np.ndarray] = []

    for fp_idx, platform in enumerate(platforms):
        fp_name = f"FP{fp_idx + 1}"

        # Stack (3, N) arrays per variable → (n_vars, 3, N),
        # then reshape + ravel to match var → axis → frame order.
        # Derive frame count from the actual data, not the point header.
        stacked = np.stack(
            [platform.get(key, np.zeros((3, 1))) for key in var_keys]
        )
        n_fp_frames = stacked.shape[2]
        stacked = stacked.reshape(-1)  # (n_vars * 3 * n_fp_frames,)

        n_fp_rows = n_vars * n_axes * n_fp_frames
        frame_idx = np.arange(n_fp_frames)

        frames_parts.append(np.tile(frame_idx, n_vars * n_axes))
        times_parts.append(np.tile(frame_idx, n_vars * n_axes) / analog_rate)
        fp_names_parts.append(np.full(n_fp_rows, fp_name, dtype="U16"))
        variables_parts.append(np.repeat(var_names, n_axes * n_fp_frames))
        axes_parts.append(np.tile(np.repeat(axis_names, n_fp_frames), n_vars))
        values_parts.append(stacked)

    if not frames_parts:
        return pl.DataFrame()

    return pl.DataFrame({
        "frame": np.concatenate(frames_parts).astype(int),
        "time": np.concatenate(times_parts),
        "fp_name": np.concatenate(fp_names_parts),
        "variable": np.concatenate(variables_parts),
        "axis": np.concatenate(axes_parts),
        "value": np.concatenate(values_parts),
        "trial_name": trial_name,
        "subject_id": subject_id,
        "session_id": session_id,
    })


def read_events(c3d_path: str | Path, trial_name: str, subject_id: str, session_id: str) -> pl.DataFrame:
    """Read gait events from C3D file and return DataFrame.
    
    Returns DataFrame with columns:
    context, label, time, trial_name, subject_id, session_id
    """
    c3d = ezc3d.c3d(str(c3d_path))
    
    contexts = get_param_strings(c3d, ["EVENT", "CONTEXTS"])
    labels = get_param_strings(c3d, ["EVENT", "LABELS"])
    times = get_param_list(c3d, ["EVENT", "TIMES"])
    
    if not isinstance(times, np.ndarray) or times.ndim != 2 or times.shape[1] == 0:
        return pl.DataFrame()
    
    # Convert times to seconds
    times_sec = times[0, :] + times[1, :] / 60.0
    
    # Pad contexts and labels to match times length
    n_events = times.shape[1]
    contexts = contexts[:n_events] + [""] * (n_events - len(contexts))
    labels = labels[:n_events] + [""] * (n_events - len(labels))
    
    return pl.DataFrame({
        "context": contexts,
        "label": labels,
        "time": times_sec.tolist(),
        "trial_name": trial_name,
        "subject_id": subject_id,
        "session_id": session_id,
    })


def read_session_params(c3d_path: str | Path) -> dict:
    """Extract PROCESSING parameters from C3D file.
    
    Returns dict of parameter name -> value (float or str).
    """
    c3d = ezc3d.c3d(str(c3d_path))
    
    params = {}
    processing = c3d.get("parameters", {}).get("PROCESSING", {})
    
    for param_name, param_info in processing.items():
        if param_name == "USED":
            continue
        value = param_info.get("value")
        if value is None:
            continue
        
        # Convert to scalar
        if isinstance(value, np.ndarray):
            value = value.flat[0] if value.size == 1 else str(value)
        
        # Try to convert to float
        try:
            params[param_name] = float(value)
        except (ValueError, TypeError):
            params[param_name] = str(value)
    
    return params
