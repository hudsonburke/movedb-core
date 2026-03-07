import numpy as np
from functools import cached_property
from pydantic import BaseModel, Field, PositiveInt, PositiveFloat, model_validator
from typing import Self
from .shapes import Array1D, NArray1D, Array3D, NArray3D


class MarkerData(BaseModel):
    """Marker trajectory data structure."""

    data: NArray3D = Field(
        description="Marker positions array of shape (n_frames, n_markers, 3) - xyz coordinates"
    )
    names: list[str] = Field(
        description="List of marker names corresponding to second dimension of data"
    )
    rate: PositiveFloat = Field(description="Sampling rate in Hz")
    units: str = Field(description="Position units (e.g., 'mm', 'm')")
    first_frame: PositiveInt = Field(
        description="First frame number in the trial", default=1
    )
    residuals: NArray1D | None = Field(
        description="Optional residuals array of shape (n_frames, n_markers)",
        default=None,
    )

    def get_index(self, marker_name: str) -> int:
        """Get the index of a marker by name."""
        try:
            return self.names.index(marker_name)
        except ValueError:
            raise ValueError(f"Marker name '{marker_name}' not found in names.")

    def get_data(self, marker_name: str) -> Array3D:
        index = self.get_index(marker_name)
        return np.asarray(self.data)[:, index, :]

    @cached_property
    def num_frames(self) -> int:
        """Return the number of frames in the data."""
        return np.asarray(self.data).shape[0]

    @cached_property
    def time_vector(self) -> Array1D:
        """Generate time vector based on rate and number of frames."""
        return (
            np.arange(self.num_frames) / self.rate
        )  # TODO: should first_frame be considered?

    @model_validator(mode="after")
    def check_shapes(self) -> Self:
        """Validate array dimensions match metadata."""
        data = np.asarray(self.data)
        n_frames, n_markers, dims = data.shape

        if dims != 3:
            raise ValueError(
                f"Data must be 3D (n_frames, n_markers, 3). Got shape {data.shape}"
            )

        if len(self.names) != n_markers:
            raise ValueError(
                f"Mismatch: {len(self.names)} marker names provided, "
                f"but data array has {n_markers} markers."
            )

        if self.residuals is not None:
            residuals = np.asarray(self.residuals)
            if residuals.shape != (n_frames, n_markers):
                raise ValueError(
                    f"Residuals shape {residuals.shape} does not match "
                    f"expected data shape ({n_frames}, {n_markers})."
                )
        return self
