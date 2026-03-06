"""Functions for reading C3D files and producing pure Pydantic data models."""

import re
from typing import Any
import ezc3d
import numpy as np
from ..core import AnalogData, Event, ForceplateData, MarkerData, TrialData


# TODO:
class NotFoundError(Exception): ...


# TODO: Expected type parameter?
# TODO: Optimize parameter access especially for indexed parameters
def get_param_list(c3d: ezc3d.c3d, keys: list[str], default=[]) -> list[Any]:
    param: dict = c3d.parameters
    for key in keys:
        param = param.get(key, {})
    value = param.get("value", default)
    return value


def get_param(c3d: ezc3d.c3d, keys: list[str], index: int = 0, default=None) -> Any:
    """
    Get nested parameters from a C3D object.

    Args:
        c3d: ezc3d.c3d object containing C3D data
        keys: Sequence of keys to access nested parameters
        index: Optional index for array parameters
        default: Default value if parameter not found

    Returns:
        Parameter value or default

    Raises:
        IndexError: If index is out of range for array parameters
    """
    param_list = get_param_list(c3d, keys)
    if index < 0 or index >= len(param_list):
        raise IndexError(f"Index {index} out of range for parameter '{keys}'")
    return param_list[index] or default


# TODO:
def extract_event_time(c3d: ezc3d.c3d, index: int) -> float:
    return 0.0


# TODO: Maybe just do all events and have individual access happen through core model
def extract_event(c3d: ezc3d.c3d, index: int) -> Event:
    """
    Extract a single event from C3D file.

    Args:
        index: Index of the event in the EVENT parameter group.

    Returns:
        Event model instance with time as float seconds.

    Raises:
        ValueError: If EVENT parameters are missing or invalid.
    """
    if "EVENT" not in c3d.parameters:
        raise ValueError("C3D object does not contain EVENT parameters")

    # Get time in seconds from (min, sec) format
    times = get_param(c3d, ["EVENT", "TIMES"], default=[[None, None]])
    if isinstance(times, np.ndarray):
        if times.ndim < 2 or times.shape[1] <= index:
            raise ValueError(f"No time data for event at index {index}")
        time_min, time_sec = times[:, index]
    else:
        if not times or len(times) < 2 or len(times[0]) <= index:
            raise ValueError(f"No time data for event at index {index}")
        time_min = times[0][index] if len(times[0]) > index else None
        time_sec = times[1][index] if len(times[1]) > index else None

    if time_min is None or time_sec is None:
        raise ValueError(f"Invalid time data for event at index {index}")

    return Event(
        context=get_param(c3d, ["EVENT", "CONTEXTS"], index=index, default=""),
        label=get_param(c3d, ["EVENT", "LABELS"], index=index, default=""),
        time=float(time_min) * 60.0 + float(time_sec),
        description=get_param(c3d, ["EVENT", "DESCRIPTIONS"], index=index, default=""),
    )


def extract_events(c3d: ezc3d.c3d) -> list[Event]:
    labels = get_param(c3d, ["EVENT", "LABELS"], default=[])
    return [extract_event(c3d, i) for i in range(len(labels))]


def extract_markers(c3d: ezc3d.c3d) -> MarkerData:
    """
    Extract marker trajectory data from the C3D.

    Returns:
        MarkerData with (n_frames, n_markers, 3) data array,
        or None if no marker data is present.
    """
    # ezc3d stores point data as shape (4, n_markers, n_frames)
    # where row 0=x, 1=y, 2=z, 3=residual
    raw_points = c3d.data.get("points")
    if raw_points is None:
        raise ValueError("Points not found in data.")

    return MarkerData(
        data=np.transpose(raw_points[:3, :, :], (2, 1, 0)).astype(np.float64),
        marker_names=get_param_list(c3d, ["POINT", "LABELS"], default=[]),
        rate=float(get_param(c3d, ["POINT", "RATE"], default=0.0)),
        units=get_param(c3d, ["POINT", "UNITS"], index=0, default="mm"),
        first_frame=int(c3d.header["points"]["first_frame"]),
        residuals=np.transpose(raw_points[3, :, :], (1, 0)).astype(np.float64),
    )


# TODO: De-dupe forceplate data so it doesn't also show up in analogs
def extract_analogs(c3d: ezc3d.c3d) -> AnalogData:
    """
    Extract analog channel data from the C3D.

    Returns:
        AnalogData with (n_frames, n_channels) data array,
        or None if no analog data is present.
    """
    raw_analogs = c3d.data.get("analogs")
    if raw_analogs is None:
        raise ValueError("No analog data found in c3d object.")

    return AnalogData(
        data=raw_analogs[0, :, :].T.astype(np.float64),
        channel_names=get_param_list(c3d, ["ANALOG", "LABELS"], default=[]),
        rate=float(get_param(c3d, ["ANALOG", "RATE"], default=0.0)),
        units=get_param(c3d, ["ANALOG", "UNITS"], index=0, default="V"),
        first_frame=int(c3d.header["points"]["first_frame"]),
    )


# TODO:
def sanitize_fp_name(name: str) -> str:
    return name.replace(" ", "_").replace("[", "").replace("]", "")


def _extract_forceplate_names(
    c3d: ezc3d.c3d, analog_descriptions: list[str]
) -> list[str]:
    """
    Extract forceplate names from analog channel descriptions.

    Many C3D files include forceplate identifiers in the ANALOG:DESCRIPTIONS
    parameter, such as "Bertec Force Plate [2]". This method extracts unique
    forceplate names by finding the first channel of each platform.

    Args:
        analog_descriptions: List of analog channel descriptions

    Returns:
        List of forceplate names in platform order, or empty list if extraction fails.
    """
    if not analog_descriptions:
        return []

    try:
        channel_mapping = get_param_list(c3d, ["FORCE_PLATFORM", "CHANNEL"])
        if len(channel_mapping) == 0:
            return []

        n_platforms = channel_mapping.shape[1] if len(channel_mapping.shape) > 1 else 0
        if n_platforms == 0:
            return []

        forceplate_names = []
        for platform_idx in range(n_platforms):
            first_channel_idx = int(channel_mapping[0, platform_idx]) - 1
            if first_channel_idx < len(analog_descriptions):
                desc = analog_descriptions[first_channel_idx]
                match = re.search(r"(.*Force\s*Plate\s*\[?\d+\]?)", desc, re.IGNORECASE)
                if match:
                    forceplate_names.append(match.group(1).strip())
                else:
                    forceplate_names.append(desc.strip())
            else:
                return []

        return forceplate_names

    except (KeyError, IndexError, AttributeError):
        return []


def extract_analog_rate(c3d: ezc3d.c3d) -> float:
    analog_rate = float(get_param(c3d, ["ANALOG", "RATE"], default=0.0))
    if analog_rate <= 0:
        # Fall back to point rate * analog-per-frame ratio
        point_rate = float(get_param(c3d, ["POINT", "RATE"], default=0.0))
        ratio = float(get_param(c3d, ["ANALOG", "RATIO"], default=1.0))
        analog_rate = point_rate * ratio
    return analog_rate


# TODO: Turn this into one object instead of dict
def extract_forceplates(c3d: ezc3d.c3d) -> dict[str, ForceplateData]:
    """
    Extract force plate data from the C3D file.

    """
    platforms = c3d.data.get("platform")
    if not platforms:
        raise ValueError("No platform data found.")

    n_platforms = len(platforms)

    # Determine forceplate names
    analog_descriptions: list[str] = get_param_list(c3d, ["ANALOG", "DESCRIPTIONS"])
    fp_names = _extract_forceplate_names(analog_descriptions)

    if not fp_names or len(fp_names) != n_platforms:
        fp_names = [f"FP_{i}" for i in range(n_platforms)]

    fp_names = [sanitize_fp_name(name) for name in fp_names]

    # Get static platform metadata
    origins = get_param_list(c3d, ["FORCE_PLATFORM", "ORIGIN"])
    corners = get_param_list(c3d, ["FORCE_PLATFORM", "CORNERS"])
    cal_matrices = get_param_list(c3d, ["FORCE_PLATFORM", "CAL_MATRIX"])

    result: dict[str, ForceplateData] = {}

    for i, platform in enumerate(platforms):
        # ezc3d platform dict has keys: 'force', 'moment', 'center_of_pressure'
        # Each is shape (3, 1, n_frames)
        forces_raw = platform.get("force")  # (3, 1, n_frames)
        moments_raw = platform.get("moment")  # (3, 1, n_frames)
        cop_raw = platform.get("center_of_pressure")  # (3, 1, n_frames)

        if forces_raw is None or moments_raw is None or cop_raw is None:
            continue

        # Reshape: (3, 1, n_frames) -> (n_frames, 3)
        forces = forces_raw[:, 0, :].T.astype(np.float64)
        moments = moments_raw[:, 0, :].T.astype(np.float64)
        cop = cop_raw[:, 0, :].T.astype(np.float64)

        # Extract per-platform metadata
        # origin: shape (3, n_platforms) in the C3D parameter
        if origins is not None and origins.shape[1] > i:
            origin = origins[:, i].astype(np.float64)
        else:
            origin = np.zeros(3, dtype=np.float64)

        # corners: shape (3, 4, n_platforms)
        if corners is not None and corners.shape[2] > i:
            corner = corners[:, :, i].T.astype(np.float64)  # (4, 3)
        else:
            corner = np.zeros((4, 3), dtype=np.float64)

        # cal_matrix: shape (6, 6, n_platforms) or may not exist
        if (
            cal_matrices is not None
            and cal_matrices.ndim == 3
            and cal_matrices.shape[2] > i
        ):
            cal = cal_matrices[:, :, i].astype(np.float64)  # (6, 6)
        else:
            cal = np.eye(6, dtype=np.float64)

        result[fp_names[i]] = ForceplateData(
            forces=forces,
            moments=moments,
            cop=cop,
            cal_matrix=cal,
            corners=corner,
            origin=origin,
            rate=extract_analog_rate(c3d),
        )
    return result


def extract_parameters(c3d: ezc3d.c3d) -> dict[str, Any]:
    """
    Extract PROCESSING parameters from the C3D file.

    The PROCESSING group is used by Vicon (and some other systems)
    to store subject-specific parameters like mass, height, and
    marker-placement offsets. These are session-level metadata.

    Returns:
        Dictionary of parameter name -> value.
    """
    parameters: dict[str, Any] = {}
    if "PROCESSING" not in c3d.parameters:
        return parameters

    for key, value in c3d.parameters["PROCESSING"].items():
        arr = value.get("value", None)
        if arr is not None and hasattr(arr, "__len__") and len(arr) == 1:
            parameters[key] = arr[0]
        else:
            parameters[key] = arr

    return parameters


def create_trial(c3d: ezc3d.c3d, name: str, trial_type: str) -> TrialData:
    return TrialData(
        name=name,
        trial_type=trial_type,
        markers=extract_markers(c3d),
        analogs=extract_analogs(c3d),
        forceplates=extract_forceplates(c3d),
        events=extract_events(c3d),
    )
