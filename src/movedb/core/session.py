"""Session data structure for biomechanical capture sessions."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, model_validator

from .trial import TrialData


class SessionData(BaseModel):
    """
    Data for a single capture session.

    A session represents one visit to the lab for a given subject.
    All trials within a session share the same subject parameters
    (mass, height, etc.) and typically the same marker set and
    hardware configuration.
    """

    subject: str = Field(description="Subject identifier (e.g., 'sub-01')")
    session: str = Field(description="Session identifier (e.g., 'ses-01')")
    date: datetime | None = Field(
        default=None,
        description="Date/time of the capture session",
    )

    # Subject parameters at time of session
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Subject parameters for this session (e.g., mass, height, leg_length)",
    )

    # Marker protocol info
    marker_set: list[str] = Field(
        default_factory=list,
        description="Expected marker names for this session (union of all trials)",
    )

    # Trials
    trials: list[TrialData] = Field(
        default_factory=list,
        description="Trials recorded during this session",
    )

    @model_validator(mode="after")
    def validate_unique_trial_names(self):
        """Ensure all trial names within a session are unique."""
        names = [trial.name for trial in self.trials]
        duplicates = [name for name in names if names.count(name) > 1]
        if duplicates:
            unique_dupes = sorted(set(duplicates))
            raise ValueError(
                f"Duplicate trial names within session: {unique_dupes}"
            )
        return self

    def get_trial(self, name: str) -> TrialData:
        """
        Get a trial by name.

        Args:
            name: Trial name to look up.

        Returns:
            The matching TrialData instance.

        Raises:
            KeyError: If no trial with that name exists.
        """
        for trial in self.trials:
            if trial.name == name:
                return trial
        raise KeyError(
            f"Trial '{name}' not found in session. "
            f"Available trials: {[t.name for t in self.trials]}"
        )

    @property
    def trial_names(self) -> list[str]:
        """List of trial names in this session."""
        return [trial.name for trial in self.trials]
