"""HDF5 storage layer for time-series biomechanics data."""

from pathlib import Path
import h5py
import numpy as np
from typing import Any
from datetime import timedelta
from loguru import logger


class HDF5TrialStorage:
    """Manages HDF5 storage for a single trial."""

    def __init__(self, hdf5_path: Path | str, trial_id: int, mode: str = "r"):
        """
        Initialize HDF5 storage.

        Args:
            hdf5_path: Path to HDF5 file
            trial_id: Unique trial identifier
            mode: 'r' (read), 'w' (write), 'a' (append)
        """
        self.hdf5_path = Path(hdf5_path)
        self.trial_id = trial_id
        self.mode = mode
        self._file: h5py.File  # Will be set in __enter__

    def __enter__(self) -> "HDF5TrialStorage":
        """Open HDF5 file."""
        try:
            # Create parent directory if needed (for write/append modes)
            if self.mode in ("w", "a"):
                self.hdf5_path.parent.mkdir(parents=True, exist_ok=True)

            self._file = h5py.File(self.hdf5_path, self.mode)
            return self
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"HDF5 file not found: {self.hdf5_path}. "
                f"Ensure the file exists or use mode='w' to create it."
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to open HDF5 file: {self.hdf5_path}. "
                f"The file may be corrupted or opened by another process."
            ) from e

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close HDF5 file."""
        if hasattr(self, "_file"):
            self._file.close()

    def _require_group(self, item) -> h5py.Group:
        """Type guard to ensure item is an HDF5 Group."""
        if not isinstance(item, h5py.Group):
            raise TypeError(f"Expected HDF5 Group, got {type(item).__name__}")
        return item

    def _require_dataset(self, item) -> h5py.Dataset:
        """Type guard to ensure item is an HDF5 Dataset."""
        if not isinstance(item, h5py.Dataset):
            raise TypeError(f"Expected HDF5 Dataset, got {type(item).__name__}")
        return item

    def write_markers(
        self,
        data: np.ndarray,
        marker_names: list[str],
        rate: float,
        units: str = "mm",
        first_frame: int = 0,
        residuals: np.ndarray | None = None,
    ) -> None:
        """
        Write marker data to HDF5.

        Args:
            data: Array of shape (n_frames, n_markers, 3) - xyz coordinates
            marker_names: List of marker names
            rate: Sampling rate in Hz
            units: Position units
            first_frame: First frame number
            residuals: Optional residuals array (n_frames, n_markers)
        """
        # Validate shapes
        if data.shape[1] != len(marker_names):
            raise ValueError(
                f"Data has {data.shape[1]} markers but {len(marker_names)} names provided"
            )
        if data.shape[2] != 3:
            raise ValueError(f"Expected 3D coordinates, got shape {data.shape}")
        # Validate rate
        if rate <= 0:
            raise ValueError(f"Rate must be positive, got {rate}")
        # Validate residuals shape if provided
        if residuals is not None:
            if residuals.shape != (data.shape[0], data.shape[1]):
                raise ValueError(
                    f"Residuals shape {residuals.shape} doesn't match "
                    f"expected {(data.shape[0], data.shape[1])}"
                )

        grp = self._file.require_group("markers")

        # Store data with compression
        if "data" in grp:
            del grp["data"]
        grp.create_dataset("data", data=data, compression="gzip", compression_opts=4)

        # Store residuals if provided
        if residuals is not None:
            if "residuals" in grp:
                del grp["residuals"]
            grp.create_dataset(
                "residuals", data=residuals, compression="gzip", compression_opts=4
            )

        # Store metadata as attributes
        grp.attrs["marker_names"] = np.array(marker_names, dtype="S")
        grp.attrs["rate"] = rate
        grp.attrs["units"] = units
        grp.attrs["first_frame"] = first_frame
        grp.attrs["n_markers"] = len(marker_names)
        grp.attrs["n_frames"] = data.shape[0]

        logger.debug(
            f"Wrote {len(marker_names)} markers, {data.shape[0]} frames to {self.hdf5_path}"
        )

    def read_markers(self) -> dict[str, Any]:
        """
        Read marker data from HDF5.

        Returns:
            Dict with keys: 'data', 'marker_names', 'rate', 'units', 'residuals'
        """
        if "markers" not in self._file:
            raise ValueError(
                f"No marker data in {self.hdf5_path}. "
                f"Available groups: {list(self._file.keys())}"
            )
        grp = self._require_group(self._file["markers"])
        data_ds = self._require_dataset(grp["data"])
        marker_names_attr = grp.attrs["marker_names"]

        result = {
            "data": data_ds[:],
            "marker_names": [name.decode("utf-8") for name in marker_names_attr],  # type: ignore
            "rate": grp.attrs["rate"],
            "units": grp.attrs["units"],
            "first_frame": grp.attrs["first_frame"],
        }

        if "residuals" in grp:
            residuals_ds = self._require_dataset(grp["residuals"])
            result["residuals"] = residuals_ds[:]

        return result

    def get_marker_by_name(self, marker_name: str) -> np.ndarray | None:
        """
        Get data for a specific marker.

        Args:
            marker_name: Name of the marker

        Returns:
            Array of shape (n_frames, 3) or None if not found
        """
        grp = self._require_group(self._file["markers"])
        marker_names_attr = grp.attrs["marker_names"]
        marker_names = [name.decode("utf-8") for name in marker_names_attr]  # type: ignore

        if marker_name not in marker_names:
            return None

        idx = marker_names.index(marker_name)
        data_ds = self._require_dataset(grp["data"])
        return data_ds[:, idx, :]

    def write_analogs(
        self,
        data: np.ndarray,
        channel_names: list[str],
        rate: float,
        units: str = "V",
        first_frame: int = 0,
    ) -> None:
        """
        Write analog data to HDF5.

        Args:
            data: Array of shape (n_frames, n_channels)
            channel_names: List of channel names
            rate: Sampling rate in Hz
            units: Signal units
            first_frame: First frame number
        """
        if data.shape[1] != len(channel_names):
            raise ValueError(
                f"Data has {data.shape[1]} channels but {len(channel_names)} names provided"
            )
        if rate <= 0:
            raise ValueError(f"Rate must be positive, got {rate}")

        grp = self._file.require_group("analogs")

        if "data" in grp:
            del grp["data"]
        grp.create_dataset("data", data=data, compression="gzip", compression_opts=4)

        grp.attrs["channel_names"] = np.array(channel_names, dtype="S")
        grp.attrs["rate"] = rate
        grp.attrs["units"] = units
        grp.attrs["first_frame"] = first_frame
        grp.attrs["n_channels"] = len(channel_names)
        grp.attrs["n_frames"] = data.shape[0]

        logger.debug(
            f"Wrote {len(channel_names)} analog channels, {data.shape[0]} frames"
        )

    def read_analogs(self) -> dict[str, Any]:
        """Read analog data from HDF5."""
        if "analogs" not in self._file:
            raise ValueError(
                f"No analog data in {self.hdf5_path}. "
                f"Available groups: {list(self._file.keys())}"
            )
        grp = self._require_group(self._file["analogs"])
        data_ds = self._require_dataset(grp["data"])
        channel_names_attr = grp.attrs["channel_names"]

        return {
            "data": data_ds[:],
            "channel_names": [name.decode("utf-8") for name in channel_names_attr],  # type: ignore
            "rate": grp.attrs["rate"],
            "units": grp.attrs["units"],
            "first_frame": grp.attrs["first_frame"],
        }

    def write_forceplate(
        self,
        name: str,
        forces: np.ndarray,
        moments: np.ndarray,
        cop: np.ndarray,
        rate: float,
        cal_matrix: np.ndarray,
        corners: np.ndarray,
        origin: np.ndarray,
        unit_force: str = "N",
        unit_moment: str = "Nm",
        unit_position: str = "m",
    ) -> None:
        """
        Write force plate data to HDF5.

        Args:
            name: Force plate identifier (e.g., "FP1")
            forces: Array of shape (n_frames, 3) - force vectors
            moments: Array of shape (n_frames, 3) - moment vectors
            cop: Array of shape (n_frames, 3) - center of pressure
            rate: Sampling rate in Hz
            cal_matrix: Calibration matrix (6, 6)
            corners: Corner coordinates (4, 3)
            origin: Origin coordinates (3,)
        """
        n_frames = forces.shape[0]
        if moments.shape[0] != n_frames or cop.shape[0] != n_frames:
            raise ValueError(
                f"Inconsistent frame counts: forces={forces.shape[0]}, "
                f"moments={moments.shape[0]}, cop={cop.shape[0]}"
            )
        if forces.shape[1] != 3 or moments.shape[1] != 3 or cop.shape[1] != 3:
            raise ValueError("Forces, moments, and COP must have shape (n_frames, 3)")
        if cal_matrix.shape != (6, 6):
            raise ValueError(
                f"Calibration matrix must be (6, 6), got {cal_matrix.shape}"
            )
        if corners.shape != (4, 3):
            raise ValueError(f"Corners must be (4, 3), got {corners.shape}")
        if origin.shape != (3,):
            raise ValueError(f"Origin must be (3,), got {origin.shape}")
        if rate <= 0:
            raise ValueError(f"Rate must be positive, got {rate}")

        fp_group = self._file.require_group(f"forceplates/{name}")

        # Store time-series data
        for ds_name, data in [("forces", forces), ("moments", moments), ("cop", cop)]:
            if ds_name in fp_group:
                del fp_group[ds_name]
            fp_group.create_dataset(
                ds_name, data=data, compression="gzip", compression_opts=4
            )

        # Store calibration data (no compression - small arrays)
        fp_group.attrs["cal_matrix"] = cal_matrix
        fp_group.attrs["corners"] = corners
        fp_group.attrs["origin"] = origin

        # Store metadata
        fp_group.attrs["rate"] = rate
        fp_group.attrs["unit_force"] = unit_force
        fp_group.attrs["unit_moment"] = unit_moment
        fp_group.attrs["unit_position"] = unit_position
        fp_group.attrs["n_frames"] = forces.shape[0]

        logger.debug(f"Wrote force plate '{name}', {forces.shape[0]} frames")

    def read_forceplate(self, name: str) -> dict[str, Any]:
        """Read force plate data from HDF5."""
        if f"forceplates/{name}" not in self._file:
            available_fps = []
            if "forceplates" in self._file:
                fp_grp = self._require_group(self._file["forceplates"])
                available_fps = list(fp_grp.keys())
            raise ValueError(
                f"No force plate '{name}' in {self.hdf5_path}. "
                f"Available force plates: {available_fps}"
            )
        fp_group = self._require_group(self._file[f"forceplates/{name}"])

        forces_ds = self._require_dataset(fp_group["forces"])
        moments_ds = self._require_dataset(fp_group["moments"])
        cop_ds = self._require_dataset(fp_group["cop"])

        return {
            "forces": forces_ds[:],
            "moments": moments_ds[:],
            "cop": cop_ds[:],
            "cal_matrix": fp_group.attrs["cal_matrix"],
            "corners": fp_group.attrs["corners"],
            "origin": fp_group.attrs["origin"],
            "rate": fp_group.attrs["rate"],
            "unit_force": fp_group.attrs["unit_force"],
            "unit_moment": fp_group.attrs["unit_moment"],
            "unit_position": fp_group.attrs["unit_position"],
        }

    def list_forceplates(self) -> list[str]:
        """List all force plates in the file."""
        if "forceplates" not in self._file:
            return []
        fp_group = self._require_group(self._file["forceplates"])
        return list(fp_group.keys())

    def write_events(self, events: list[dict]) -> None:
        """
        Write event data to HDF5.

        Args:
            events: List of event dicts with keys: context, label, time, description
        """
        grp = self._file.require_group("metadata")

        # Convert events to structured array for efficient storage
        if events:
            dtype = [
                ("context", "S64"),
                ("label", "S64"),
                ("time_seconds", "f8"),
                ("description", "S256"),
            ]

            event_array = np.array(
                [
                    (
                        e["context"].encode("utf-8"),
                        e["label"].encode("utf-8"),
                        e["time"].total_seconds()
                        if isinstance(e["time"], timedelta)
                        else e["time"],
                        e.get("description", "").encode("utf-8"),
                    )
                    for e in events
                ],
                dtype=dtype,
            )

            if "events" in grp:
                del grp["events"]
            grp.create_dataset("events", data=event_array)

        logger.debug(f"Wrote {len(events)} events")

    def read_events(self) -> list[dict]:
        """Read events from HDF5."""
        grp = self._file.get("metadata")
        if grp is None:
            return []

        grp = self._require_group(grp)
        if "events" not in grp:
            return []

        events_dataset = self._require_dataset(grp["events"])
        events_array = events_dataset[:]
        return [
            {
                "context": e["context"].decode("utf-8"),
                "label": e["label"].decode("utf-8"),
                "time": timedelta(seconds=float(e["time_seconds"])),
                "description": e["description"].decode("utf-8"),
            }
            for e in events_array
        ]


def get_trial_hdf5_path(trial_id: int, base_dir: Path) -> Path:
    """
    Generate HDF5 file path for a trial.

    Organizes files in subdirectories: base_dir/trials_000000/trial_000001.h5

    Args:
        trial_id: Trial ID
        base_dir: Base directory for HDF5 storage

    Returns:
        Path to HDF5 file
    """
    # Group trials in folders of 1000 (trial_0000-0999, trial_1000-1999, etc.)
    folder_id = (trial_id // 1000) * 1000
    folder_name = f"trials_{folder_id:06d}"

    trial_dir = base_dir / folder_name
    trial_dir.mkdir(parents=True, exist_ok=True)

    return trial_dir / f"trial_{trial_id:06d}.h5"
