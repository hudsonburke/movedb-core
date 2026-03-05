import ezc3d
from datetime import datetime, timedelta
from typing import Any
import numpy as np
from ..core import Event, Trial, CaptureSession, Subject
from pydantic import BaseModel, ConfigDict


def get_param(
    c3d: ezc3d.c3d, *keys: str, index: int | None = None, default: Any = None
) -> Any:
    """
    Get nested parameters from the C3D object.

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

    if index is not None and (isinstance(value, list) or isinstance(value, np.ndarray)):
        if index < 0 or index >= len(value):
            raise IndexError(f"Index {index} out of range for parameter '{keys}'")
        return value[index]
    return value


# TODO: This shouldn't be a class
class C3DAdapter(BaseModel):
    """
    Adapter class for converting C3D file data to MoveDB models.
    Handles parameter access, error handling, and data conversion.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    c3d: ezc3d.c3d

    @classmethod
    def from_file(
        cls, file_path: str, extract_forceplat_data: bool = True
    ) -> "C3DAdapter":
        """Convenience method"""
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
        param: dict = self.c3d.parameters
        for key in keys:
            param = param.get(key, {})
        value = param.get("value", default)

        if index is not None and (
            isinstance(value, list) or isinstance(value, np.ndarray)
        ):
            if index < 0 or index >= len(value):
                raise IndexError(f"Index {index} out of range for parameter '{keys}'")
            return value[index]
        return value

    def get_event(self, trial: Trial, index: int = 0) -> Event:
        """
        Extract event data from C3D file.

        Args:
            index: Index of the event to extract

        Returns:
            Event model instance

        Raises:
            ValueError: If EVENT parameters are missing or invalid
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
            # Handle list format
            if not times or len(times) < 2 or len(times[0]) <= index:
                raise ValueError(f"No time data for event at index {index}")
            time_min = times[0][index] if len(times[0]) > index else None
            time_sec = times[1][index] if len(times[1]) > index else None
        if time_min is None or time_sec is None:
            raise ValueError(f"Invalid time data for event at index {index}")

        description = self.get_param("EVENT", "DESCRIPTIONS", index=index, default="")

        return Event(
            trial=trial,
            context=context,
            label=label,
            time=timedelta(minutes=time_min, seconds=time_sec),
            description=description,
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
            List of forceplate names in platform order, or empty list if extraction fails
        """
        import re

        if not analog_descriptions:
            return []

        # Get channel mapping to determine which channels belong to each platform
        try:
            channel_mapping = self.get_param("FORCE_PLATFORM", "CHANNEL", default=None)
            if channel_mapping is None or len(channel_mapping) == 0:
                return []

            # channel_mapping is shape (6, n_platforms) where each column is a platform
            # and contains the 1-indexed analog channel numbers for Fx, Fy, Fz, Mx, My, Mz
            n_platforms = (
                channel_mapping.shape[1] if len(channel_mapping.shape) > 1 else 0
            )

            if n_platforms == 0:
                return []

            forceplate_names = []
            for platform_idx in range(n_platforms):
                # Get the first channel (Fx) for this platform (1-indexed in C3D)
                first_channel_idx = int(channel_mapping[0, platform_idx]) - 1

                # Get the description for this channel
                if first_channel_idx < len(analog_descriptions):
                    desc = analog_descriptions[first_channel_idx]

                    # Try to extract a clean forceplate name
                    # Look for patterns like "Bertec Force Plate [2]" or "Force Plate 3"
                    match = re.search(
                        r"(.*Force\s*Plate\s*\[?\d+\]?)", desc, re.IGNORECASE
                    )
                    if match:
                        forceplate_names.append(match.group(1).strip())
                    else:
                        # If no pattern match, use the full description
                        forceplate_names.append(desc.strip())
                else:
                    # Channel index out of range, fall back to generic name
                    return []

            return forceplate_names

        except (KeyError, IndexError, AttributeError):
            # If anything goes wrong, return empty list to trigger fallback
            return []

    def get_all_events(self, trial: Trial) -> list[Event]:
        """
        Extract all events from C3D file.

        Returns:
            List of Event instances
        """
        n_events = len(self.get_param("EVENT", "LABELS", default=[]))
        return [self.get_event(trial=trial, index=i) for i in range(n_events)]

    def to_trial(
        self,
        name: str = "",
        timestamp: datetime | None = None,
        capture_session: CaptureSession | None = None,
        subjects: list[Subject] | None = None,
        trial_id: int | None = None,
    ) -> Trial:
        """
        Convert the C3D data to a Trial instance with HDF5 storage.

        Args:
            name: Trial name
            timestamp: Trial timestamp
            capture_session: Associated capture session
            subjects: Associated subjects
            trial_id: Trial ID (required for HDF5 path generation)

        Returns:
            Trial instance with metadata and HDF5 path reference
        """
        if subjects is None:
            subjects = []

        # Extract metadata parameters
        parameters = {}
        # The PROCESSING group is not an official C3D parameter group, but Vicon uses it for subject parameters
        if "PROCESSING" in self.c3d.parameters:
            for key, value in self.c3d.parameters["PROCESSING"].items():
                arr = value.get("value", None)
                if arr is not None and len(arr) == 1:
                    parameters[key] = arr[0]
                else:
                    parameters[key] = arr

        # Extract marker metadata
        marker_labels = self.get_param("POINT", "LABELS", default=[])
        marker_rate = self.get_param("POINT", "RATE", default=0.0)
        marker_units = self.get_param("POINT", "UNITS", index=0, default="m")

        # Extract analog metadata
        analog_labels = self.get_param("ANALOG", "LABELS", default=[])
        analog_descriptions = self.get_param("ANALOG", "DESCRIPTIONS", default=[])
        analog_rate = self.get_param("ANALOG", "RATE", default=0.0)

        # Extract forceplate metadata
        forceplate_names = []
        forceplate_rate = analog_rate  # Force plates use analog rate
        if "platform" in self.c3d.data:
            # Try to extract forceplate names from analog channel descriptions
            forceplate_names = self._extract_forceplate_names(analog_descriptions)

            # Fall back to generic names if extraction failed
            if not forceplate_names or len(forceplate_names) != len(
                self.c3d.data["platform"]
            ):
                forceplate_names = [
                    f"ForcePlate_{i}" for i in range(len(self.c3d.data["platform"]))
                ]

            # Sanitize names immediately for OpenSim compatibility and consistency
            # Remove special characters that cause issues: brackets, etc.
            forceplate_names = [
                name.replace(" ", "_").replace("[", "").replace("]", "")
                for name in forceplate_names
            ]

        # Get frame info
        first_frame = self.c3d.header["points"]["first_frame"]
        last_frame = self.c3d.header["points"]["last_frame"]
        n_frames = last_frame - first_frame + 1

        # Create Trial model with metadata
        trial = Trial(
            id=trial_id,
            name=name,
            timestamp=timestamp,
            capture_session=capture_session,
            subjects=subjects,
            parameters=parameters,
            marker_names=marker_labels,
            analog_names=analog_labels,
            forceplate_names=forceplate_names,
            marker_rate=marker_rate,
            analog_rate=analog_rate,
            forceplate_rate=forceplate_rate,
            n_frames=n_frames,
            first_frame=first_frame,
            last_frame=last_frame,
        )

        # Extract events (stay in SQL - lightweight)
        trial.events = self.get_all_events(trial=trial)

        return trial
