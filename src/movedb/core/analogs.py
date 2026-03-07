import numpy as np
from functools import cached_property
from pydantic import BaseModel, Field, model_validator, PositiveInt, PositiveFloat
from typing import Self
from .shapes import Array1D, NArray1D


class AnalogData(BaseModel):
    """Analog signal data structure."""

    names: list[str] = Field(
        description="List of channel names corresponding to second dimension of data"
    )
    data: NArray1D = Field(
        description="Analog signals array of shape (n_frames, n_channels)"
    )
    rate: PositiveFloat = Field(description="Sampling rate in Hz")
    units: str = Field(description="Signal units (e.g., 'V', 'mV')")
    first_frame: PositiveInt = Field(description="First frame number in the trial")

    def get_index(self, name: str) -> int:
        """Get the index of a channel by name."""
        try:
            return self.names.index(name)
        except ValueError:
            raise ValueError(f"Name '{name}' not found in name list.")

    def get_data(self, name: str) -> Array1D:
        index = self.get_index(name)
        return np.asarray(self.data)[:, index]

    @cached_property
    def num_frames(self) -> int:
        """Return the number of frames in the data."""
        return np.asarray(self.data).shape[0]

    @cached_property
    def time_vector(self) -> Array1D:
        """Generate time vector based on rate and number of frames."""
        return np.arange(self.num_frames) / self.rate

    @model_validator(mode="after")
    def check_shapes(self) -> Self:
        """Validate array dimensions match metadata."""
        data = np.asarray(self.data)
        _, n_channels = data.shape

        if len(self.names) != n_channels:
            raise ValueError(
                f"Mismatch: {len(self.names)} channel names provided, "
                f"but data array has {n_channels} channels."
            )
        return self
