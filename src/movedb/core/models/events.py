"""Event data structures for biomechanical trials."""
from .trial import Trial
from pydantic import model_validator
from sqlmodel import SQLModel, Field, Relationship

class Event(SQLModel, table=True):
    """
    Times will default to being stored in seconds.
    See c3d event specification for details.

    Exactly one of 'frame' or 'time' must be provided.
    """
    trial: Trial = Relationship(back_populates="events")

    context: str
    label: str
    frame: int | None = Field(default=None, description="Frame number")
    time: float | None = Field(default=None, description="Time in seconds")
    description: str | None = None

    @model_validator(mode="after")
    def validate_exactly_one_temporal_field(self):
        """Ensure exactly one of frame or time is provided."""
        fields_provided = sum([self.frame is not None, self.time is not None])

        if fields_provided == 0:
            raise ValueError("Exactly one of 'frame' or 'time' must be provided")
        elif fields_provided > 1:
            raise ValueError("Only one of 'frame' or 'time' may be provided, not both")

        return self

    def get_frame(self, point_rate: float | None) -> int:
        if self.frame is not None:
            return self.frame
        if self.time is not None and point_rate is not None and point_rate > 0:
            return int(self.time * point_rate)
        # This should not happen if validate_frames_or_times is called first
        raise ValueError("Cannot compute frame without point rate or time.")

    def get_time(self, point_rate: float | None) -> float:
        if self.time is not None:
            return self.time
        if self.frame is not None and point_rate is not None and point_rate > 0:
            return self.frame / point_rate
        # This should not happen if validate_frames_or_times is called first
        raise ValueError("Cannot compute time without point rate or frame.")
