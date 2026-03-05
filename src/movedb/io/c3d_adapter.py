"""Adapter for reading C3D files and producing pure Pydantic data models."""

import re
from typing import Any

import ezc3d
import numpy as np
from pydantic import BaseModel, ConfigDict

from ..core import AnalogData, Event, ForceplateData, MarkerData, TrialData


def get_param(
    c3d: ezc3d.c3d, *keys: str, index: int | None = None, default: Any = None
) -> Any:
    """
    Get nested parameters from a C3D object.

    Args:
        c3d: ezc3d.c3d object containing C3D data
        *keys: Sequence of keys to access nested parameters
        index: Optional index for array parameters
        default: Default value if parameter not found

    Returns:
        Parameter value or default

    Raises:
        IndexError: If index is out of range for array parameters
    """
    param: dict = c3d.parameters
    for key in keys:
        param = param.get(key, {})
    value = param.get("value", default)

    if index is not None and isinstance(value, (list, np.ndarray)):
        if index < 0 or index >= len(value):
            raise IndexError(f"Index {index} out of range for parameter '{keys}'")
        return value[index]
    return value


class C3DAdapter(BaseModel):
    """
    Adapter for converting C3D file data to MoveDB core models.

    Reads an ezc3d object and produces TrialData with actual signal data
    (markers, analogs, forceplates) as numpy arrays, plus events and metadata.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    c3d: ezc3d.c3d

    @classmethod
    def from_file(
        cls, file_path: str, extract_forceplat_data: bool = True
    ) -> "C3DAdapter":
        """Create adapter from a C3D file path."""
        c3d_obj = ezc3d.c3d(file_path, extract_forceplat_data=extract_forceplat_data)
        return cls(c3d=c3d_obj)

    def get_param(
        self, *keys: str, index: int | None = None, default: Any = None
    ) -> Any:
        """
        Get nested parameters from the C3D object.

        Args:
            *keys: Sequence of keys to access nested parameters
            index: Optional index for array parameters
            default: Default value if parameter not found

        Returns:
            Parameter value or default

        Raises:
            IndexError: If index is out of range for array parameters
        """
        return get_param(self.c3d, *keys, index=index, default=default)

    # ------------------------------------------------------------------
    # Event extraction
    # ------------------------------------------------------------------

    def _extract_event(self, index: int) -> Event:
        """
        Extract a single event from C3D file.

        Args:
            index: Index of the event in the EVENT parameter group.

        Returns:
            Event model instance with time as float seconds.

        Raises:
            ValueError: If EVENT parameters are missing or invalid.
        """
        if "EVENT" not in self.c3d.parameters:
            raise ValueError("C3D object does not contain EVENT parameters")

        context = self.get_param("EVENT", "CONTEXTS", index=index, default="")
        label = self.get_param("EVENT", "LABELS", index=index, default="")

        # Get time in seconds from (min, sec) format
        times = self.get_param("EVENT", "TIMES", default=[[None, None]])
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

        time_seconds = float(time_min) * 60.0 + float(time_sec)

        description = self.get_param("EVENT", "DESCRIPTIONS", index=index, default="")

        return Event(
            context=context,
            label=label,
            time=time_seconds,
            description=description or None,
        )

    def extract_events(self) -> list[Event]:
        """
        Extract all events from the C3D file.

        Returns:
            List of Event instances with times as float seconds.
        """
        labels = self.get_param("EVENT", "LABELS", default=[])
        if not labels:
            return []
        return [self._extract_event(i) for i in range(len(labels))]

    # ------------------------------------------------------------------
    # Signal data extraction
    # ------------------------------------------------------------------

    def extract_markers(self) -> MarkerData | None:
        """
        Extract marker trajectory data from the C3D file.

        Returns:
            MarkerData with (n_frames, n_markers, 3) data array,
            or None if no marker data is present.
        """
        # ezc3d stores point data as shape (4, n_markers, n_frames)
        # where row 0=x, 1=y, 2=z, 3=residual
        raw_points = self.c3d.data.get("points")
        if raw_points is None:
            return None

        marker_labels: list[str] = self.get_param("POINT", "LABELS", default=[])
        if not marker_labels:
            return None

        rate = float(self.get_param("POINT", "RATE", default=0.0))
        if rate <= 0:
            return None

        units: str = self.get_param("POINT", "UNITS", index=0, default="mm")
        first_frame: int = int(self.c3d.header["points"]["first_frame"])
        # Ensure first_frame is at least 1 for PositiveInt
        if first_frame < 1:
            first_frame = 1

        # raw_points shape: (4, n_markers, n_frames) -> need (n_frames, n_markers, 3)
        xyz = raw_points[:3, :, :]  # (3, n_markers, n_frames)
        data = np.transpose(xyz, (2, 1, 0)).astype(np.float64)  # (n_frames, n_markers, 3)

        # Only keep markers that have labels (ezc3d may pad with unlabeled markers)
        n_labeled = len(marker_labels)
        if data.shape[1] > n_labeled:
            data = data[:, :n_labeled, :]

        # Extract residuals: row 3 of raw_points
        residuals_raw = raw_points[3, :n_labeled, :]  # (n_markers, n_frames)
        residuals = np.transpose(residuals_raw, (1, 0)).astype(np.float64)  # (n_frames, n_markers)

        return MarkerData(
            data=data,
            marker_names=marker_labels,
            rate=rate,
            units=units,
            first_frame=first_frame,
            residuals=residuals,
        )

    def extract_analogs(self) -> AnalogData | None:
        """
        Extract analog channel data from the C3D file.

        Returns:
            AnalogData with (n_frames, n_channels) data array,
            or None if no analog data is present.
        """
        # ezc3d stores analog data as shape (1, n_channels, n_frames)
        raw_analogs = self.c3d.data.get("analogs")
        if raw_analogs is None:
            return None

        channel_names: list[str] = self.get_param("ANALOG", "LABELS", default=[])
        if not channel_names:
            return None

        rate = float(self.get_param("ANALOG", "RATE", default=0.0))
        if rate <= 0:
            return None

        units: str = self.get_param("ANALOG", "UNITS", index=0, default="V")
        first_frame: int = int(self.c3d.header["points"]["first_frame"])
        if first_frame < 1:
            first_frame = 1

        # raw_analogs shape: (1, n_channels, n_frames) -> need (n_frames, n_channels)
        data = raw_analogs[0, :, :].T.astype(np.float64)  # (n_frames, n_channels)

        # Only keep channels that have labels
        n_labeled = len(channel_names)
        if data.shape[1] > n_labeled:
            data = data[:, :n_labeled]

        return AnalogData(
            data=data,
            channel_names=channel_names,
            rate=rate,
            units=units,
            first_frame=first_frame,
        )

    def _extract_forceplate_names(self, analog_descriptions: list[str]) -> list[str]:
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
            channel_mapping = self.get_param("FORCE_PLATFORM", "CHANNEL", default=None)
            if channel_mapping is None or len(channel_mapping) == 0:
                return []

            n_platforms = (
                channel_mapping.shape[1] if len(channel_mapping.shape) > 1 else 0
            )
            if n_platforms == 0:
                return []

            forceplate_names = []
            for platform_idx in range(n_platforms):
                first_channel_idx = int(channel_mapping[0, platform_idx]) - 1
                if first_channel_idx < len(analog_descriptions):
                    desc = analog_descriptions[first_channel_idx]
                    match = re.search(
                        r"(.*Force\s*Plate\s*\[?\d+\]?)", desc, re.IGNORECASE
                    )
                    if match:
                        forceplate_names.append(match.group(1).strip())
                    else:
                        forceplate_names.append(desc.strip())
                else:
                    return []

            return forceplate_names

        except (KeyError, IndexError, AttributeError):
            return []

    def extract_forceplates(self) -> dict[str, ForceplateData]:
        """
        Extract force plate data from the C3D file.

        Returns:
            Dictionary mapping plate name to ForceplateData.
            Empty dict if no force platform data is present.
        """
        platforms = self.c3d.data.get("platform")
        if not platforms:
            return {}

        n_platforms = len(platforms)

        # Determine forceplate names
        analog_descriptions: list[str] = self.get_param(
            "ANALOG", "DESCRIPTIONS", default=[]
        )
        fp_names = self._extract_forceplate_names(analog_descriptions)
        if not fp_names or len(fp_names) != n_platforms:
            fp_names = [f"FP_{i}" for i in range(n_platforms)]

        # Sanitize names: remove brackets, replace spaces with underscores
        fp_names = [
            name.replace(" ", "_").replace("[", "").replace("]", "")
            for name in fp_names
        ]

        # Get analog rate (forceplates use analog sampling rate)
        analog_rate = float(self.get_param("ANALOG", "RATE", default=0.0))
        if analog_rate <= 0:
            # Fall back to point rate * analog-per-frame ratio
            point_rate = float(self.get_param("POINT", "RATE", default=0.0))
            ratio = float(self.get_param("ANALOG", "RATIO", default=1.0))
            analog_rate = point_rate * ratio

        # Get static platform metadata
        origins = self.get_param("FORCE_PLATFORM", "ORIGIN", default=None)
        corners = self.get_param("FORCE_PLATFORM", "CORNERS", default=None)
        cal_matrices = self.get_param("FORCE_PLATFORM", "CAL_MATRIX", default=None)

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
            if cal_matrices is not None and cal_matrices.ndim == 3 and cal_matrices.shape[2] > i:
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
                rate=analog_rate,
            )

        return result

    # ------------------------------------------------------------------
    # Parameter extraction (for session-level metadata)
    # ------------------------------------------------------------------

    def extract_parameters(self) -> dict[str, Any]:
        """
        Extract PROCESSING parameters from the C3D file.

        The PROCESSING group is used by Vicon (and some other systems)
        to store subject-specific parameters like mass, height, and
        marker-placement offsets. These are session-level metadata.

        Returns:
            Dictionary of parameter name -> value.
        """
        parameters: dict[str, Any] = {}
        if "PROCESSING" not in self.c3d.parameters:
            return parameters

        for key, value in self.c3d.parameters["PROCESSING"].items():
            arr = value.get("value", None)
            if arr is not None and hasattr(arr, "__len__") and len(arr) == 1:
                parameters[key] = arr[0]
            else:
                parameters[key] = arr

        return parameters

    # ------------------------------------------------------------------
    # High-level conversion
    # ------------------------------------------------------------------

    def to_trial(self, name: str = "", trial_type: str = "") -> TrialData:
        """
        Convert the C3D data to a TrialData instance with all signal data.

        Extracts markers, analogs, forceplates, and events from the C3D
        file and returns a fully-populated TrialData model.

        Args:
            name: Trial name (e.g., 'Walk_01').
            trial_type: Type of trial (e.g., 'static', 'walking').

        Returns:
            TrialData instance with numpy arrays and event list.
        """
        return TrialData(
            name=name,
            trial_type=trial_type,
            markers=self.extract_markers(),
            analogs=self.extract_analogs(),
            forceplates=self.extract_forceplates(),
            events=self.extract_events(),
        )
