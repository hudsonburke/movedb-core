"""Event data structures for biomechanical trials."""

from pydantic import BaseModel, Field, model_validator, PositiveFloat, PositiveInt


class Event(BaseModel):
    """
    A discrete event within a biomechanical trial.

    Times are stored as float seconds from trial onset.
    See C3D event specification for details.

    Exactly one of 'frame' or 'time' must be provided.
    """

    context: str = Field(description="Event context (e.g., 'Left', 'Right', 'General')")
    label: str = Field(description="Event label (e.g., 'Foot Strike', 'Foot Off')")
    frame: PositiveInt | None = Field(default=None, description="Frame number")
    time: float | None = Field(
        default=None,
        description="Time in seconds from the start of the trial",
    )
    description: str | None = Field(
        default=None, description="Optional event description"
    )

    @model_validator(mode="after")
    def validate_exactly_one_temporal_field(self):
        """Ensure exactly one of frame or time is provided."""
        has_frame = self.frame is not None
        has_time = self.time is not None

        if not has_frame and not has_time:
            raise ValueError("Exactly one of 'frame' or 'time' must be provided")
        if has_frame and has_time:
            raise ValueError("Only one of 'frame' or 'time' may be provided, not both")
        return self

    def get_frame(self, rate: PositiveFloat | None = None) -> int:
        """Get the frame number, computing from time and rate if necessary."""
        if self.frame is not None:
            return self.frame
        if self.time is not None and rate is not None and rate > 0:
            return int(self.time * rate)
        raise ValueError("Cannot compute frame without rate or time.")

    def get_time(self, rate: PositiveFloat | None = None) -> float:
        """Get the time in seconds, computing from frame and rate if necessary."""
        if self.time is not None:
            return self.time
        if self.frame is not None and rate is not None and rate > 0:
            return self.frame / rate
        raise ValueError("Cannot compute time without rate or frame.")
