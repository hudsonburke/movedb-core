import numpy as np
from typing import Self
from pydantic import BaseModel, Field, model_validator, PositiveFloat, PositiveInt
from functools import cached_property
from .shapes import (
    Array1D,
    Array3D,
    NArray3D,
    Origin,
    NOrigins,
    Corners,
    NCorners,
    CalMatrix,
    NCalMatrix,
)


class ForceplateData(BaseModel):
    """Forceplate data structure."""

    names: list[str] = Field(
        description="List of force plate names corresponding to second dimension of data arrays"
    )
    forces: NArray3D = Field(
        description="Force vectors array of shape (n_frames, n_plates, 3) - xyz components"
    )
    moments: NArray3D = Field(
        description="Moment vectors array of shape (n_frames, n_plates, 3) - xyz components"
    )
    cop: NArray3D = Field(
        description="Center of pressure array of shape (n_frames, n_plates, 3) - xyz coordinates"
    )
    cal_matrices: NCalMatrix = Field(
        description="Calibration matrices of shape (6, n_plates, 6)"
    )
    corners: NCorners = Field(
        description="Corner coordinates of shape (4, n_plates, 3) - xyz for each corner"
    )
    origins: NOrigins = Field(
        description="Origin coordinates of shape (3, n_plates) - xyz per plate"
    )
    rate: PositiveFloat = Field(description="Sampling rate in Hz")
    first_frame: PositiveInt = Field(
        description="First frame number in the trial", default=1
    )

    unit_force: str = Field(description="Force units (e.g., 'N')", default="N")
    unit_moment: str = Field(description="Moment units (e.g., 'Nm')", default="Nm")
    unit_position: str = Field(
        description="Position units (e.g., 'm', 'mm')", default="m"
    )

    @cached_property
    def data(self) -> np.ndarray:
        """Combined forces/moments/cop concatenated along last axis: (n_frames, n_plates, 9)."""
        return np.concatenate(
            [np.asarray(a) for a in [self.forces, self.moments, self.cop]], axis=2
        )

    def get_index(self, name: str) -> int:
        """Get the index of a plate by name."""
        try:
            return self.names.index(name)
        except ValueError:
            raise ValueError(f"Name '{name}' not found in list.")

    def get_data(self, name: str) -> Array3D:
        index = self.get_index(name)
        return np.asarray(self.data)[:, index, :]

    def get_origin(self, name: str) -> Origin:
        index = self.get_index(name)
        return np.asarray(self.origins)[:, index]

    def get_corners(self, name: str) -> Corners:
        index = self.get_index(name)
        return np.asarray(self.corners)[:, index]

    def get_cal_matrix(self, name: str) -> CalMatrix:
        index = self.get_index(name)
        return np.asarray(self.cal_matrices)[:, index, :]

    @cached_property
    def num_frames(self) -> int:
        return np.asarray(self.forces).shape[0]

    @cached_property
    def frame_vector(self) -> Array1D:
        return np.arange(self.num_frames) + self.first_frame

    @cached_property
    def time_vector(self) -> Array1D:
        return np.arange(self.num_frames) / self.rate

    @model_validator(mode="after")
    def dims_must_match(self) -> Self:
        forces = np.asarray(self.forces)
        force_frames, n_forces, _ = forces.shape

        moments = np.asarray(self.moments)
        moment_frames, n_moments, _ = moments.shape
        if moment_frames != force_frames:
            raise ValueError(
                f"Moments frames {moment_frames} do not match forces frames {force_frames}."
            )
        if n_moments != n_forces:
            raise ValueError(
                f"Number of moment plates {n_moments} does not match number of force plates {n_forces}."
            )
        cop = np.asarray(self.cop)
        cop_frames, n_cop, _ = cop.shape
        if cop_frames != force_frames:
            raise ValueError(
                f"CoP frames {cop_frames} do not match forces frames {force_frames}."
            )
        if n_cop != n_forces:
            raise ValueError(
                f"Number of CoP plates {n_cop} does not match number of force plates {n_forces}."
            )

        if len(self.names) != n_forces:
            raise ValueError(
                f"Mismatch: {len(self.names)} plate names provided, "
                f"but data arrays have {n_forces} plates."
            )
        return self
