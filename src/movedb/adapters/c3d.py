"""Functions for reading C3D files and producing pure Pydantic data models."""

from typing import Any

import ezc3d
import numpy as np

from ..core import AnalogData, Event, ForceplateData, MarkerData, TrialData

import logging

logger = logging.getLogger(__name__)


def get_param_list(
    c3d: ezc3d.c3d, keys: list[str], default: list | None = None
) -> list[Any] | np.ndarray:
    """Navigate nested C3D parameters and return the ``value`` list.

    Args:
        c3d: ezc3d.c3d object.
        keys: Parameter group path, e.g. ``["POINT", "LABELS"]``.
        default: Fallback when the parameter value is missing.
            ``None`` is treated as ``[]``.

    Returns:
        The parameter value (usually a list or numpy array), or *default*.
    """
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
    """Like :func:`get_param_list` but guarantees a ``list[str]`` return.

    Useful for LABELS, DESCRIPTIONS, and UNITS parameters that are always
    string lists in C3D files.
    """
    value = get_param_list(c3d, keys)
    if isinstance(value, np.ndarray):
        return [str(v) for v in value.flat]
    if value is None or len(value) == 0:
        return default if default is not None else []
    return [str(v) for v in value]


def get_param(c3d: ezc3d.c3d, keys: list[str], index: int = 0, default=None) -> Any:
    """Get a single indexed value from a C3D parameter list.

    Args:
        c3d: ezc3d.c3d object containing C3D data.
        keys: Parameter group path, e.g. ``["POINT", "RATE"]``.
        index: Index into the parameter's value list.
        default: Default value if the parameter is missing or empty.

    Returns:
        Parameter value, or *default* when the value is ``None``.

    Raises:
        IndexError: If *index* is out of range for a non-empty parameter list.
    """
    param_list = get_param_list(c3d, keys)
    if not hasattr(param_list, "__len__") or len(param_list) == 0:
        return default
    if index < 0 or index >= len(param_list):
        raise IndexError(f"Index {index} out of range for parameter '{keys}'")
    value = param_list[index]
    return value if value is not None else default


def extract_event(c3d: ezc3d.c3d, index: int) -> Event:
    """Extract a single event from a C3D file.

    Args:
        index: Index of the event in the EVENT parameter group.

    Returns:
        Event model instance with time as float seconds.

    Raises:
        ValueError: If EVENT parameters are missing or invalid.
    """
    if "EVENT" not in c3d.parameters:
        raise ValueError("C3D object does not contain EVENT parameters")

    # EVENT:TIMES is a (2, n_events) array — row 0 = minutes, row 1 = seconds.
    # We access the raw value directly; routing through get_param would index
    # into rows rather than events.
    times = get_param_list(c3d, ["EVENT", "TIMES"])
    if isinstance(times, np.ndarray):
        if times.ndim < 2 or times.shape[1] <= index:
            raise ValueError(f"No time data for event at index {index}")
        time_min, time_sec = times[:, index]
    else:
        raise ValueError(
            f"EVENT:TIMES is not a numpy array (got {type(times).__name__})"
        )

    return Event(
        context=get_param(c3d, ["EVENT", "CONTEXTS"], index=index, default=""),
        label=get_param(c3d, ["EVENT", "LABELS"], index=index, default=""),
        time=float(time_min) * 60.0 + float(time_sec),
        description=get_param(c3d, ["EVENT", "DESCRIPTIONS"], index=index, default=""),
    )


def extract_events(c3d: ezc3d.c3d) -> list[Event]:
    """Extract all events from a C3D file."""
    labels = get_param_strings(c3d, ["EVENT", "LABELS"])
    if not labels or len(labels) == 0:
        return []
    return [extract_event(c3d, i) for i in range(len(labels))]


def extract_markers(c3d: ezc3d.c3d) -> MarkerData:
    """Extract marker trajectory data from the C3D.

    ezc3d layout::

        c3d['data']['points']              — (4, n_markers, n_frames)
            rows: X, Y, Z, homogeneous coordinate (1.0)
        c3d['data']['meta_points']['residuals'] — (1, n_markers, n_frames)

    Returns:
        MarkerData with ``data`` shaped ``(n_frames, n_markers, 3)``.
    """
    raw_points = c3d["data"]["points"]  # (4, n_markers, n_frames)

    # Residuals: (1, N, T) → squeeze axis 0 → (N, T) → transpose → (T, N)
    residuals = None
    try:
        raw_residuals = c3d["data"]["meta_points"]["residuals"]
        residuals = np.squeeze(raw_residuals, axis=0).T.astype(np.float64)
    except (KeyError, TypeError):
        pass

    return MarkerData(
        # (4, N, T)[:3] → (3, N, T) → transpose(2,1,0) → (T, N, 3)
        data=np.transpose(raw_points[:3, :, :], (2, 1, 0)).astype(np.float64),
        names=get_param_strings(c3d, ["POINT", "LABELS"]),
        descriptions=get_param_strings(c3d, ["POINT", "DESCRIPTIONS"]),
        rate=float(get_param(c3d, ["POINT", "RATE"], default=0.0)),
        units=get_param(c3d, ["POINT", "UNITS"], index=0, default="mm"),
        first_frame=int(c3d["header"]["points"]["first_frame"]),
        residuals=residuals,
    )


def extract_analog_rate(c3d: ezc3d.c3d) -> float:
    """Extract the analog sampling rate, falling back to point_rate * ratio."""
    analog_rate = float(get_param(c3d, ["ANALOG", "RATE"], default=0.0))
    if analog_rate <= 0:
        point_rate = float(get_param(c3d, ["POINT", "RATE"], default=0.0))
        ratio = float(get_param(c3d, ["ANALOG", "RATIO"], default=1.0))
        analog_rate = point_rate * ratio
    return analog_rate


def extract_analogs(c3d: ezc3d.c3d) -> AnalogData:
    """Extract analog channel data from the C3D.

    ezc3d layout::

        c3d['data']['analogs'] — (1, n_channels, n_frames)

    Returns:
        AnalogData with ``data`` shaped ``(n_frames, n_channels)``.
    """
    raw_analogs = c3d["data"]["analogs"]  # (1, n_channels, n_frames)

    return AnalogData(
        data=raw_analogs[0, :, :].T.astype(np.float64),  # → (n_frames, n_channels)
        names=get_param_strings(c3d, ["ANALOG", "LABELS"]),
        rate=extract_analog_rate(c3d),
        units=get_param_strings(c3d, ["ANALOG", "UNITS"]),
        descriptions=get_param_strings(c3d, ["ANALOG", "DESCRIPTIONS"]),
        first_frame=int(c3d["header"]["points"]["first_frame"]),
    )


def sanitize_fp_name(name: str) -> str:
    """Sanitize a forceplate name for use as a column identifier."""
    return name.replace(" ", "_").replace("[", "").replace("]", "")


def find_forceplate_names(c3d: ezc3d.c3d, n_platforms: int) -> list[str]:
    """Derive human-readable forceplate names from ANALOG:DESCRIPTIONS.

    Uses the first analog channel index per plate (from
    ``FORCE_PLATFORM:CHANNEL``) to look up a description.  Falls back to
    generic ``FP_0``, ``FP_1``, ... when descriptions are unavailable or
    don't match the number of platforms.
    """
    # FORCE_PLATFORM:CHANNEL is (n_channels_per_plate, n_plates), e.g. (6, 4)
    # Values are 1-based analog channel indices.
    channel_arr = get_param_list(c3d, ["FORCE_PLATFORM", "CHANNEL"])
    analog_descriptions = get_param_strings(c3d, ["ANALOG", "DESCRIPTIONS"])

    fp_names: list[str] = []
    if (
        analog_descriptions
        and isinstance(channel_arr, np.ndarray)
        and channel_arr.ndim == 2
    ):
        # Take the first channel per plate (row 0) as representative
        first_channels = channel_arr[0, :]  # shape (n_plates,)
        seen: set[str] = set()
        for idx in first_channels:
            adj = int(idx) - 1  # convert to 0-based
            if 0 <= adj < len(analog_descriptions):
                name = sanitize_fp_name(analog_descriptions[adj])
                if name and name not in seen:
                    fp_names.append(name)
                    seen.add(name)

    if len(fp_names) != n_platforms:
        fp_names = [f"FP_{i}" for i in range(n_platforms)]

    return fp_names


def extract_forceplates(c3d: ezc3d.c3d) -> ForceplateData:
    """Extract force plate data from the C3D file.

    Relies on ezc3d's platform parsing (requires
    ``extract_forceplat_data=True`` when loading).

    ezc3d per-platform shapes::

        force / moment / center_of_pressure / Tz : (3, n_frames)
        origin  : (3,)
        corners : (3, 4)
        cal_matrix : (6, 6)  — may be (0,) if absent

    Returns a single ForceplateData container with stacked arrays:

    - forces, moments, cop : ``(n_frames, n_plates, 3)``
    - free_moment : ``(n_frames, n_plates, 3)`` or ``None``
    - origins : ``(3, n_plates)``
    - corners : ``(4, n_plates, 3)``
    - cal_matrices : ``(6, n_plates, 6)``
    """
    platforms = c3d["data"]["platform"]
    if not platforms:
        raise ValueError(
            "No platform data found. "
            "Make sure you set 'extract_forceplat_data=True' when loading the C3D file."
        )

    n = len(platforms)
    r = range(n)

    # Time-series: per-plate (3, T) → stack axis=1 → (3, n, T) → transpose → (T, n, 3)
    forces = (
        np.stack([platforms[i]["force"] for i in r], axis=1)
        .transpose(2, 1, 0)
        .astype(np.float64)
    )
    moments = (
        np.stack([platforms[i]["moment"] for i in r], axis=1)
        .transpose(2, 1, 0)
        .astype(np.float64)
    )
    cop = (
        np.stack([platforms[i]["center_of_pressure"] for i in r], axis=1)
        .transpose(2, 1, 0)
        .astype(np.float64)
    )

    # Tz (free moment) — may be absent or all zeros
    free_moment = None
    try:
        fm = (
            np.stack([platforms[i]["Tz"] for i in r], axis=1)
            .transpose(2, 1, 0)
            .astype(np.float64)
        )
        if np.any(fm != 0):
            free_moment = fm
    except (KeyError, IndexError):
        pass

    # Origins: per-plate (3,) → stack axis=1 → (3, n)
    origins = np.stack([platforms[i]["origin"] for i in r], axis=1).astype(np.float64)

    # Corners: per-plate (3, 4) → stack axis=1 → (3, n, 4) → transpose → (4, n, 3)
    corners = (
        np.stack([platforms[i]["corners"] for i in r], axis=1)
        .transpose(2, 1, 0)
        .astype(np.float64)
    )

    # Cal matrices: per-plate (6, 6) or (0,) → stack axis=1 → (6, n, 6)
    cal_mats = [platforms[i]["cal_matrix"] for i in r]
    cal_mats = [m if m.ndim == 2 else np.zeros((6, 6)) for m in cal_mats]
    cal_matrices = np.stack(cal_mats, axis=1).astype(np.float64)

    return ForceplateData(
        names=find_forceplate_names(c3d, n),
        forces=forces,
        moments=moments,
        cop=cop,
        free_moment=free_moment,
        origins=origins,
        corners=corners,
        cal_matrices=cal_matrices,
        rate=extract_analog_rate(c3d),
        first_frame=int(c3d["header"]["points"]["first_frame"]),
        units_force=[platforms[i].get("unit_force", "N") for i in r],
        units_moment=[platforms[i].get("unit_moment", "Nmm") for i in r],
        units_position=[platforms[i].get("unit_position", "mm") for i in r],
    )


def extract_processing_parameters(c3d: ezc3d.c3d) -> dict[str, Any]:
    """Extract PROCESSING parameters from the C3D file.

    The PROCESSING group is used by Vicon (and some other systems)
    to store subject-specific parameters like mass, height, and
    marker-placement offsets.

    Returns:
        Dictionary of parameter name -> value.
    """
    parameters: dict[str, Any] = {}
    if "PROCESSING" not in c3d.parameters:
        raise ValueError("C3D object does not contain PROCESSING parameters")

    for key, value in c3d.parameters["PROCESSING"].items():
        arr = value.get("value", None)
        if arr is not None and hasattr(arr, "__len__") and len(arr) == 1:
            parameters[key] = arr[0]
        else:
            parameters[key] = arr

    return parameters


def create_trial(c3d: ezc3d.c3d, name: str) -> TrialData:
    """Create a TrialData model from a loaded C3D object."""
    return TrialData(
        name=name,
        markers=extract_markers(c3d),
        analogs=extract_analogs(c3d),
        forceplates=extract_forceplates(c3d),
        events=extract_events(c3d),
    )
