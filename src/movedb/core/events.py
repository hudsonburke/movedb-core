"""Event data structures for biomechanical trials."""
from typing import TYPE_CHECKING
from pydantic import model_validator
from sqlmodel import SQLModel, Field, Relationship
from datetime import timedelta
from sqlalchemy import Column, Interval

if TYPE_CHECKING:
    from .trial import Trial

class Event(SQLModel, table=True):
    """
    Times will default to being stored in seconds.
    See c3d event specification for details.

    Exactly one of 'frame' or 'time' must be provided.
    """
    id: int | None = Field(default=None, primary_key=True)
    trial_id: int | None = Field(default=None, foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates="events")

    context: str
    label: str
    frame: int | None = Field(default=None, description="Frame number")
    time: timedelta | None = Field(
        default=None, 
        sa_column=Column(Interval),
        description="Time from the start of the trial"
    )
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

    def get_frame(self, rate: float | None = None) -> int:
        if self.frame is not None:
            return self.frame
        if self.time is not None and rate is not None and rate > 0:
            return int(self.time.seconds * rate)
        # This should not happen if validate_frames_or_times is called first
        raise ValueError("Cannot compute frame without rate or time.")

    def get_time(self, rate: float | None = None) -> timedelta:
        if self.time is not None:
            return self.time
        if self.frame is not None and rate is not None and rate > 0:
            return timedelta(seconds=self.frame / rate)
        # This should not happen if validate_frames_or_times is called first
        raise ValueError("Cannot compute time without rate or frame.")
