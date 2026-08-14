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
        return [str(v) for v in value.flat]
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
    
    # Create arrays for each column
    frames = np.repeat(np.arange(n_frames), n_markers)
    times = np.repeat(np.arange(n_frames) / point_rate, n_markers)
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
    
    point_rate = get_param(c3d, ["POINT", "RATE"], default=100.0)
    n_frames = c3d["header"]["points"]["last_frame"] - c3d["header"]["points"]["first_frame"] + 1
    
    platforms = c3d["data"].get("platform", [])
    if not platforms:
        return pl.DataFrame()
    
    all_frames = []
    all_times = []
    all_fp_names = []
    all_variables = []
    all_axes = []
    all_values = []
    
    for fp_idx, platform in enumerate(platforms):
        fp_name = f"FP{fp_idx + 1}"
        
        for var_name, var_key in [("force", "force"), ("moment", "moment"), ("cop", "center_of_pressure")]:
            data = platform.get(var_key, np.zeros((3, n_frames)))
            
            for axis_idx, axis_name in enumerate(["x", "y", "z"]):
                all_frames.extend(range(n_frames))
                all_times.extend([i / point_rate for i in range(n_frames)])
                all_fp_names.extend([fp_name] * n_frames)
                all_variables.extend([var_name] * n_frames)
                all_axes.extend([axis_name] * n_frames)
                all_values.extend(data[axis_idx, :].tolist())
    
    if not all_frames:
        return pl.DataFrame()
    
    return pl.DataFrame({
        "frame": all_frames,
        "time": all_times,
        "fp_name": all_fp_names,
        "variable": all_variables,
        "axis": all_axes,
        "value": all_values,
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
    
    if times is None or len(times.shape) != 2 or times.shape[1] == 0:
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
