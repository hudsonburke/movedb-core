"""Event data structures for biomechanical trials."""

import ezc3d
from pydantic import BaseModel, Field, model_validator

from movedb.utils import get_c3d_param


class Event(BaseModel):
    """
    Times will default to being stored in seconds.
    See c3d event specification for details.

    Exactly one of 'frame' or 'time' must be provided.
    """

    label: str
    context: str
    frame: int | None = Field(default=None, description="Frame number")
    time: float | None = Field(default=None, description="Time in seconds")
    description: str | None = None

    @classmethod
    def from_c3d(cls, c3d_obj: ezc3d.c3d, index: int = 0) -> "Event":
        if not "EVENT" in c3d_obj.parameters:
            raise ValueError("C3D object does not contain EVENT parameters.")
        label = get_c3d_param(c3d_obj, "EVENT", "LABELS", index=index, default="")
        context = get_c3d_param(c3d_obj, "EVENT", "CONTEXTS", index=index, default="")
        # Get time in seconds from (min, sec) format
        time_min, time_sec=  get_c3d_param(
            c3d_obj, "EVENT", "TIMES", default=[[None, None]]
        )[:, index]
        if time_min is None or time_sec is None:
            raise ValueError(
                f"Invalid time data for event at index {index} in C3D object"
            )
        description = get_c3d_param(
            c3d_obj, "EVENT", "DESCRIPTIONS", index=index, default=""
        )
        return cls(
            label=label,
            context=context,
            time=time_min * 60 + time_sec,  # Convert from (min, sec) to sec
            description=description,
        )

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
