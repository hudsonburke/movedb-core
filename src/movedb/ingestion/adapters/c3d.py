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

from movedb.schemas.models import (
    AnalogsData,
    EventsData,
    ForceplateGeometryData,
    ForceplatesData,
    PointsData,
)

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


def _extract_params_group(c3d: ezc3d.c3d, group: str) -> dict:
    """Extract all parameters from a C3D parameter group.

    Returns dict of parameter name -> value (float or str).
    """
    params = {}
    group_data = c3d.get("parameters", {}).get(group, {})

    for param_name, param_info in group_data.items():
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


def read_parameters(c3d_path: str | Path) -> dict:
    """Extract parameters from a C3D file.

    Combines PROCESSING, TRIAL, and ANALOG group parameters into a single
    dict. Each C3D file contains trial-level parameters that are typically
    consistent across trials in a session but can differ.
    """
    c3d = ezc3d.c3d(str(c3d_path))

    params = {}
    for group in ("PROCESSING", "TRIAL", "ANALOG"):
        params.update(_extract_params_group(c3d, group))

    return params


def read_points(
    c3d_path: str | Path, trial_name: str
) -> pl.DataFrame:
    """Read 3D point positions from C3D file.

    Returns long-format DataFrame with columns:
    frame, time, marker_name, x, y, z, residual, camera_mask, trial_name

    Includes tracking residuals and camera visibility masks for
    data quality filtering.
    """
    c3d = ezc3d.c3d(str(c3d_path))

    point_rate = get_param(c3d, ["POINT", "RATE"], default=100.0)
    n_frames = (
        c3d["header"]["points"]["last_frame"]
        - c3d["header"]["points"]["first_frame"]
        + 1
    )
    labels = get_param_strings(c3d, ["POINT", "LABELS"])
    n_markers = len(labels)

    # Extract marker positions (4, n_markers, n_frames) — 4th row is residual
    data = c3d["data"]["points"]

    # Extract residuals (1, n_markers, n_frames)
    residuals = c3d["data"]["meta_points"]["residuals"]

    # Extract camera masks (n_cameras, n_markers, n_frames)
    camera_masks = c3d["data"]["meta_points"]["camera_masks"]

    # Create arrays for each column
    frames = np.repeat(np.arange(n_frames), n_markers)
    times = frames / point_rate
    marker_names = np.tile(labels, n_frames)
    x = data[0, :, :].T.flatten()
    y = data[1, :, :].T.flatten()
    z = data[2, :, :].T.flatten()
    residual = residuals[0, :, :].T.flatten()

    # Camera masks: convert to list of ints per row
    # camera_masks shape: (n_cameras, n_markers, n_frames)
    # Transpose to (n_frames, n_markers, n_cameras), then flatten
    mask_data = camera_masks.transpose(2, 1, 0).reshape(-1, camera_masks.shape[0])
    camera_mask = [mask.astype(int).tolist() for mask in mask_data]

    return PointsData.DataFrame(
        {
            "frame": frames.astype(int),
            "time": times,
            "marker_name": marker_names,
            "x": x.astype(float),
            "y": y.astype(float),
            "z": z.astype(float),
            "residual": residual.astype(float),
            "camera_mask": camera_mask,
            "trial_name": trial_name,
        }
    )


# Keep backward compatibility
read_markers = read_points


def read_forceplates(
    c3d_path: str | Path, trial_name: str
) -> pl.DataFrame:
    """Read force plate data from C3D file.

    Returns long-format DataFrame with columns:
    frame, time, fp_name, variable, axis, value, trial_name
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
        stacked = np.stack([platform.get(key, np.zeros((3, 1))) for key in var_keys])
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

    return ForceplatesData.DataFrame(
        {
            "frame": np.concatenate(frames_parts).astype(int),
            "time": np.concatenate(times_parts),
            "fp_name": np.concatenate(fp_names_parts),
            "variable": np.concatenate(variables_parts),
            "axis": np.concatenate(axes_parts),
            "value": np.concatenate(values_parts),
            "trial_name": trial_name,
        }
    )


def read_forceplate_geometry(
    c3d_path: str | Path, trial_name: str
) -> pl.DataFrame:
    """Read force plate calibration and positioning from C3D file.

    Returns DataFrame with columns:
    fp_name, origin, corners, cal_matrix, trial_name

    Origin is a list of 3 floats (x, y, z).
    Corners is a flattened 3x4 array (12 floats) — 4 corner points.
    Cal_matrix is a flattened 6x6 array (36 floats), or empty if not stored.
    """
    c3d = ezc3d.c3d(str(c3d_path))

    try:
        fp_used = get_param(c3d, ["FORCE_PLATFORM", "USED"], default=0)
        n_plates = int(fp_used) if fp_used is not None else 0
    except (ValueError, TypeError):
        n_plates = 0

    if n_plates == 0:
        return pl.DataFrame()

    corners_raw = get_param_list(c3d, ["FORCE_PLATFORM", "CORNERS"], default=[])
    origin_raw = get_param_list(c3d, ["FORCE_PLATFORM", "ORIGIN"], default=[])
    cal_raw = get_param_list(c3d, ["FORCE_PLATFORM", "CAL_MATRIX"], default=[])

    fp_names = []
    origins = []
    corners_list = []
    cal_matrices = []

    for fp_idx in range(n_plates):
        fp_name = f"FP{fp_idx + 1}"

        # Origin: (3, n_plates) — slice column fp_idx
        if isinstance(origin_raw, np.ndarray) and origin_raw.size > 0:
            if origin_raw.ndim == 2:
                origin = origin_raw[:, fp_idx].tolist()
            else:
                origin = origin_raw.tolist()
        else:
            origin = [0.0, 0.0, 0.0]

        # Corners: (3, 4, n_plates) — slice plate dimension, then flatten
        if isinstance(corners_raw, np.ndarray) and corners_raw.size > 0:
            if corners_raw.ndim == 3:
                # Shape is (3, 4, n_plates) — take all3 coords, 4 corners for this plate
                plate_corners = corners_raw[:, :, fp_idx]  # (3, 4)
                flat_corners = plate_corners.ravel().tolist()
            elif corners_raw.ndim == 2:
                # Shape is (3, 4*n_plates) — old format
                start = fp_idx * 4
                plate_corners = corners_raw[:, start:start + 4]  # (3, 4)
                flat_corners = plate_corners.ravel().tolist()
            else:
                flat_corners = corners_raw.ravel().tolist()[:12]
        else:
            flat_corners = [0.0] * 12

        # Cal matrix: (6, 6*n_plates) or empty — may not be stored in C3D
        if isinstance(cal_raw, np.ndarray) and cal_raw.size > 0:
            if cal_raw.ndim == 2:
                start = fp_idx * 6
                plate_cal = cal_raw[:, start:start + 6]  # (6, 6)
                flat_cal = plate_cal.ravel().tolist()
            else:
                flat_cal = cal_raw.ravel().tolist()[:36]
        else:
            flat_cal = [0.0] * 36  # use zeros instead of empty list to avoid List(Null)

        fp_names.append(fp_name)
        origins.append(origin)
        corners_list.append(flat_corners)
        cal_matrices.append(flat_cal)

    return ForceplateGeometryData.DataFrame(
        {
            "fp_name": fp_names,
            "origin": origins,
            "corners": corners_list,
            "cal_matrix": cal_matrices,
            "trial_name": [trial_name] * n_plates,
        }
    )


def read_analogs(
    c3d_path: str | Path, trial_name: str
) -> pl.DataFrame:
    """Read raw analog channel data from C3D file.

    Returns long-format DataFrame with columns:
    frame, time, channel_name, value, unit, trial_name
    """
    c3d = ezc3d.c3d(str(c3d_path))

    analog_rate = get_param(c3d, ["ANALOG", "RATE"], default=1000.0)
    n_analog_frames = c3d["header"]["analogs"]["last_frame"] - c3d["header"]["analogs"]["first_frame"] + 1

    # Get channel labels and units
    labels = get_param_strings(c3d, ["ANALOG", "LABELS"])
    units = get_param_strings(c3d, ["ANALOG", "UNITS"], default=[])

    n_channels = len(labels)

    if n_channels == 0 or n_analog_frames == 0:
        return pl.DataFrame()

    # Get raw analog data — shape (1, n_channels, n_frames)
    data = c3d["data"]["analogs"]
    if data.size == 0:
        return pl.DataFrame()

    # Build long-format arrays
    frames = np.repeat(np.arange(n_analog_frames), n_channels)
    times = frames / analog_rate
    channel_names = np.tile(labels, n_analog_frames)
    values = data[0, :, :].T.flatten()

    # Pad units to match channel count
    units_padded = units[:n_channels] + [""] * (n_channels - len(units))
    units_tiled = np.tile(units_padded, n_analog_frames)

    return AnalogsData.DataFrame(
        {
            "frame": frames.astype(int),
            "time": times,
            "channel_name": channel_names,
            "value": values.astype(float),
            "unit": units_tiled,
            "trial_name": [trial_name] * len(frames),
        }
    )


def read_events(
    c3d_path: str | Path, trial_name: str
) -> pl.DataFrame:
    """Read gait events from C3D file.

    Returns DataFrame with columns:
    context, label, time, trial_name
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

    return EventsData.DataFrame(
        {
            "context": contexts,
            "label": labels,
            "time": times_sec.tolist(),
            "trial_name": [trial_name] * n_events,
        }
    )
