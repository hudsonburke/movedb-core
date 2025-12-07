import numpy as np
from functools import cached_property
from numpy.typing import NDArray
from pydantic import (
    BaseModel,
    Field,
    model_validator,
    PositiveInt,
    PositiveFloat,
    ConfigDict,
)


class AnalogData(BaseModel):
    """Analog signal data structure."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: NDArray[np.float64] = Field(
        description="Analog signals array of shape (n_frames, n_channels)"
    )
    channel_names: list[str] = Field(
        description="List of channel names corresponding to second dimension of data"
    )
    rate: PositiveFloat = Field(description="Sampling rate in Hz")
    units: str = Field(description="Signal units (e.g., 'V', 'mV')")
    first_frame: PositiveInt = Field(description="First frame number in the trial")

    def get_channel_index(self, channel_name: str) -> int:
        """Get the index of a channel by name."""
        try:
            return self.channel_names.index(channel_name)
        except ValueError:
            raise ValueError(
                f"Channel name '{channel_name}' not found in channel_names."
            )

    def get_channel_data(self, channel_name: str) -> NDArray[np.float64]:
        index = self.get_channel_index(channel_name)
        return self.data[:, index]

    @cached_property
    def num_frames(self) -> int:
        """Return the number of frames in the data."""
        return self.data.shape[0]

    @cached_property
    def time_vector(self) -> NDArray[np.float64]:
        """Generate time vector based on rate and number of frames."""
        return np.arange(self.num_frames) / self.rate

    @model_validator(mode="after")
    def check_shapes(self) -> "AnalogData":
        """Validate array dimensions match metadata."""
        n_frames, n_channels = self.data.shape

        if len(self.channel_names) != n_channels:
            raise ValueError(
                f"Mismatch: {len(self.channel_names)} channel names provided, "
                f"but data array has {n_channels} channels."
            )
        return self
