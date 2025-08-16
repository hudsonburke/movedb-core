"""Force platform data structures."""

from typing import Annotated

import ezc3d
import numpy as np
import pandera.polars as pa
from pandera.typing.polars import DataFrame
from pydantic import AfterValidator, BaseModel
from movedb.file_io import get_units_conversion_factor
from movedb.core.shaped_arrays import (
    Corners3x4,
    Matrix6x6,
    Vector3D,
    Matrix3xN
)


class ForcePlatformSchema(pa.DataFrameModel):
    """DataFrame model for force platform data with required columns."""

    force_x: float = pa.Field(coerce=True, nullable=True)
    force_y: float = pa.Field(coerce=True, nullable=True)
    force_z: float = pa.Field(coerce=True, nullable=True)
    # Moments and center of pressure are expressed in global coordinates
    moment_x: float = pa.Field(coerce=True, nullable=True)
    moment_y: float = pa.Field(coerce=True, nullable=True)
    moment_z: float = pa.Field(coerce=True, nullable=True)
    center_of_pressure_x: float = pa.Field(coerce=True, nullable=True)
    center_of_pressure_y: float = pa.Field(coerce=True, nullable=True)
    center_of_pressure_z: float = pa.Field(coerce=True, nullable=True)
    free_moment_x: float = pa.Field(coerce=True, nullable=True)
    free_moment_y: float = pa.Field(coerce=True, nullable=True)
    free_moment_z: float = pa.Field(coerce=True, nullable=True)


ValidForcePlatformData = Annotated[
    DataFrame[ForcePlatformSchema], AfterValidator(ForcePlatformSchema.validate)
]


class EZForcePlatform(BaseModel):
    """Force platform data structure with robust shape validation.

    This class represents force platform data with the following shape requirements:
    - cal_matrix: (6, 6) - Calibration matrix for force platform transformations
    - corners: (3, 4) - 3D coordinates for the 4 corners of the force platform
    - origin: (3,) - 3D origin point of the force platform
    - data: DataFrame with 12 columns representing force, moment, COP, and free moment components

    All shape validations are enforced using Pydantic validators with clear error messages.
    """
    unit_force: str = "N"
    unit_moment: str = "Nm"
    unit_position: str = "m"
    cal_matrix: Matrix6x6 = Matrix6x6(np.eye(6))  # Calibration matrix for force platform
    corners: Corners3x4 = Corners3x4(np.zeros((3, 4)))  # 4 corners in 3D space
    origin: Vector3D = Vector3D(np.zeros(3))  # Origin of the force platform
    data: ValidForcePlatformData  # Data for the force platform

    @classmethod
    def from_c3d(cls, c3d_obj: ezc3d.c3d, index: int = 0) -> "EZForcePlatform":
        """Create an EZForcePlatform from a C3D object."""
        if not "platform" in c3d_obj.data:
            raise ValueError(
                "C3D object does not contain ezc3d platform data. Make sure to set the extract_forceplat_data=True in ezc3d.c3d constructor."
            )
        c3d_fp = c3d_obj.data["platform"]
        if index >= len(c3d_fp):
            raise IndexError(
                f"Index {index} out of range for force platforms. Available: {len(c3d_fp)}"
            )
        fp: dict = c3d_fp[index]
        force = fp.get("force", np.zeros((3, 0)))
        moment = fp.get("moment", np.zeros((3, 0)))
        position = fp.get("center_of_pressure", np.zeros((3, 0)))
        free_moment = fp.get("Tz", np.zeros((3, 0)))

        # Ensure free_moment has 3 rows (x, y, z components)
        if free_moment.ndim == 1:
            # If Tz is 1D, assume it's the z-component and pad with zeros
            n_frames = len(free_moment)
            free_moment_3d = np.zeros((3, n_frames))
            free_moment_3d[2, :] = free_moment  # Z component
            free_moment = free_moment_3d
        elif free_moment.shape[0] != 3:
            # If not 3 rows, pad or truncate to 3 rows
            n_frames = (
                free_moment.shape[1] if free_moment.ndim > 1 else len(free_moment)
            )
            free_moment_3d = np.zeros((3, n_frames))
            if free_moment.ndim > 1:
                rows_to_copy = min(3, free_moment.shape[0])
                free_moment_3d[:rows_to_copy, :] = free_moment[:rows_to_copy, :]
            free_moment = free_moment_3d

        cast_matrix = lambda x: Matrix3xN(np.asarray(x, dtype=float))

        # Create DataFrame using a cleaner mapping approach
        data_dict = cls._create_data_dict(cast_matrix(force), cast_matrix(moment), cast_matrix(position), cast_matrix(free_moment))
        return cls(
            unit_force=fp.get("unit_force", "N"),
            unit_moment=fp.get("unit_moment", "Nm"),
            unit_position=fp.get("unit_position", "m"),
            cal_matrix=fp.get("cal_matrix", np.eye(6)),
            corners=fp.get("corners", np.zeros((4, 3))),
            origin=fp.get("origin", np.zeros(3)),
            data=DataFrame[ForcePlatformSchema](data_dict),
        )

    @classmethod
    def _create_data_dict(
        cls,
        force: Matrix3xN,
        moment: Matrix3xN,
        position: Matrix3xN,
        free_moment: Matrix3xN,
    ) -> dict[str, np.ndarray]:
        """Create a data dictionary from force platform arrays.

        Expected input shape: (3, n_frames) for each array
        Output: Dictionary with 12 columns, each containing n_frames values

        This method maps the 3D arrays to the required column structure in a clean,
        maintainable way. It automatically handles the mapping from array indices
        to column names.
        """
        # Define the mapping from data arrays to column prefixes
        data_sources = [
            (force, "force"),
            (moment, "moment"),
            (position, "center_of_pressure"),
            (free_moment, "free_moment"),
        ]

        # Create the data dictionary
        data_dict = {}
        for array, prefix in data_sources:
            # Ensure array has the expected shape (3, n_frames)
            if array.size == 0:
                # Handle completely empty arrays
                for axis in ["x", "y", "z"]:
                    data_dict[f"{prefix}_{axis}"] = np.array([])
                continue

            # Ensure we have at least (3, n_frames) shape
            if array.ndim == 1:
                # Convert 1D array to (1, n_frames) and pad to (3, n_frames)
                n_frames = len(array)
                padded_array = np.zeros((3, n_frames))
                padded_array[0, :] = array  # Assume it's the first component
                array = padded_array
            elif array.shape[0] < 3:
                # Pad arrays with fewer than 3 rows
                n_frames = array.shape[1]
                padded_array = np.zeros((3, n_frames))
                padded_array[: array.shape[0], :] = array
                array = padded_array

            # Extract each axis component (each will be a 1D array of length n_frames)
            for i, axis in enumerate(["x", "y", "z"]):
                column_name = f"{prefix}_{axis}"
                data_dict[column_name] = array[i, :]  # Shape: (n_frames,)

        return data_dict

    @property
    def force(self) -> np.ndarray:
        """Return force as a numpy array (n_frames, 3)"""
        return self.data.select(["force_x", "force_y", "force_z"]).to_numpy()

    def get_force(self, units: str = "N") -> np.ndarray:
        """Return force in specified units as a numpy array (n_frames, 3)"""
        if units != self.unit_force:
            conversion_factor = get_units_conversion_factor(self.unit_force, units)
            return self.force * conversion_factor
        return self.force

    @property
    def moment(self) -> np.ndarray:
        """Return moment as a numpy array (n_frames, 3)"""
        return self.data.select(["moment_x", "moment_y", "moment_z"]).to_numpy()

    def get_moment(self, units: str = "Nm") -> np.ndarray:
        """Return moment in specified units as a numpy array (n_frames, 3)"""
        if units != self.unit_moment:
            conversion_factor = get_units_conversion_factor(self.unit_moment, units)
            return self.moment * conversion_factor
        return self.moment
    
    @property
    def center_of_pressure(self) -> np.ndarray:
        """Return center of pressure as a numpy array (n_frames, 3)"""
        return self.data.select(
            ["center_of_pressure_x", "center_of_pressure_y", "center_of_pressure_z"]
        ).to_numpy()

    def get_center_of_pressure(self, units: str = "m") -> np.ndarray:
        """Return center of pressure in specified units as a numpy array (n_frames, 3)"""
        if units != self.unit_position:
            conversion_factor = get_units_conversion_factor(self.unit_position, units)
            return self.center_of_pressure * conversion_factor
        return self.center_of_pressure
    
    @property
    def free_moment(self) -> np.ndarray:
        """Return free moment as a numpy array (n_frames, 3)"""
        return self.data.select(
            ["free_moment_x", "free_moment_y", "free_moment_z"]
        ).to_numpy()
    
    def get_free_moment(self, units: str = "Nm") -> np.ndarray:
        """Return free moment in specified units as a numpy array (n_frames, 3)"""
        if units != self.unit_moment:
            conversion_factor = get_units_conversion_factor(self.unit_moment, units)
            return self.free_moment * conversion_factor
        return self.free_moment
    
    def apply_rotation(self, rotation: np.ndarray) -> "EZForcePlatform":
        """Apply a rotation matrix to the force platform data."""
        if rotation.shape != (3, 3):
            raise ValueError("Rotation matrix must be of shape (3, 3).")

        # Apply rotation to corners and origin
        rotated_corners = rotation @ self.corners
        rotated_origin = rotation @ self.origin

        # Apply rotation to force, moment, COP, and free moment
        rotated_force = (rotation @ self.force.T).T
        rotated_moment = (rotation @ self.moment.T).T
        rotated_cop = (rotation @ self.center_of_pressure.T).T
        rotated_free_moment = (rotation @ self.free_moment.T).T

        # Create a new EZForcePlatform with the rotated data
        return EZForcePlatform(
            unit_force=self.unit_force,
            unit_moment=self.unit_moment,
            unit_position=self.unit_position,
            cal_matrix=self.cal_matrix,
            corners=rotated_corners,
            origin=rotated_origin,
            data=DataFrame[ForcePlatformSchema](
                {
                    "force_x": rotated_force[:, 0],
                    "force_y": rotated_force[:, 1],
                    "force_z": rotated_force[:, 2],
                    "moment_x": rotated_moment[:, 0],
                    "moment_y": rotated_moment[:, 1],
                    "moment_z": rotated_moment[:, 2],
                    "center_of_pressure_x": rotated_cop[:, 0],
                    "center_of_pressure_y": rotated_cop[:, 1],
                    "center_of_pressure_z": rotated_cop[:, 2],
                    "free_moment_x": rotated_free_moment[:, 0],
                    "free_moment_y": rotated_free_moment[:, 1],
                    "free_moment_z": rotated_free_moment[:, 2],
                }
            ),
        )