import numpy as np
from functools import cached_property
from typing import Literal, Self

from pydantic import Field, PositiveInt, model_validator

from .metadata import _MetaBase
from .shapes import Array1D, NArray1D


class AnalogMeta(_MetaBase):
    """Metadata for analog data, embedded in Parquet file-level metadata."""

    type: Literal["analogs"] = "analogs"
    units: str = Field(description="Signal units (e.g., 'V', 'mV')")


class AnalogData(AnalogMeta):
    """Analog signal data structure."""

    data: NArray1D = Field(
        description="Analog signals array of shape (n_frames, n_channels)"
    )
    first_frame: PositiveInt = Field(description="First frame number in the trial")

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
