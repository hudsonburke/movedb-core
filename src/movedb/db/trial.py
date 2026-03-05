from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Any, TYPE_CHECKING
import h5py as h5
import numpy as np
from .hierarchy import TrialSubjectLink
from .groups import TrialGroupLink

if TYPE_CHECKING:
    from .events import Event
    from .hierarchy import CaptureSession, Subject
    from .groups import TrialGroup


class Trial(SQLModel, table=True):
    """Trial metadata (SQL) + time-series data (HDF5)."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="", index=True)

    # Relationships (metadata only)
    capture_session_id: int | None = Field(
        default=None, foreign_key="capturesession.id"
    )
    capture_session: "CaptureSession | None" = Relationship(
        back_populates="trials"
    )
    subjects: list["Subject"] = Relationship(
        back_populates="trials", link_model=TrialSubjectLink
    )
    groups: list["TrialGroup"] = Relationship(
        back_populates="trials", link_model=TrialGroupLink
    )

    timestamp: datetime | None = None

    # Storage reference
    storage_path: str = Field(default="", description="Path to HDF5 storage file")
    storage: h5.File | None = Field(default=None, repr=False, exclude=True)

    # Event data
    events: list["Event"] = Relationship(back_populates="trial")

    def _load_storage(self):
        try:
            if self.storage is None:
                self.storage = h5.File(self.storage_path, "r")
            return True
        except Exception as e:
            raise RuntimeError(
                f"Could not load trial storage file at {self.storage_path}."
            ) from e

    @property
    def markers(self):
        self._load_storage()
        return self.storage["markers"]

    @property
    def analogs(self):
        self._load_storage()
        return self.storage["analogs"]

    @property
    def forceplates(self):
        self._load_storage()
        return self.storage["forceplates"]

    def get_events(self, label: str = "", context: str = "") -> list["Event"]:
        """
        Return a copy of the events list filtered by label and context.
        If label or context is empty, it will not filter by that parameter.
        """
        return [
            event
            for event in self.events
            if (not label or event.label == label)
            and (not context or event.context == context)
        ]

    def get_event_sequences(
        self, seq: list[tuple[str, str]], repeat: bool = False, strict: bool = False
    ) -> list[list["Event"]]:
        """
        Get sequences of events based on a list of (context, label) tuples.

        Args:
            seq: A list of (context, label) tuples defining the event sequence to find.
                 For example: [("Left", "Foot Strike"), ("Left", "Foot Off")]
            repeat: If True, find all occurrences of the sequence, including overlapping ones.
                   If False, only find the first complete occurrence.
            strict: If True, only match sequences where events appear consecutively without interruptions.
                   If False, allow other events between sequence elements.

        Returns:
            A list of event sequences, where each sequence is a list of Event objects.
            If repeat=False, the list will contain at most one sequence.
        """
        if not seq or not self.events:
            return []

        sequences = []
        event_pairs = [(event.context, event.label) for event in self.events]
        n_events = len(self.events)
        seq_len = len(seq)

        if strict:
            for start in range(n_events - seq_len + 1):
                if event_pairs[start : start + seq_len] == seq:
                    matched_events = self.events[start : start + seq_len]
                    sequences.append(matched_events)
                    if not repeat:
                        break
        else:
            search_limit = n_events - seq_len
            start_index = 0
            while start_index <= search_limit:
                matched_events = []
                first_event_found_at = -1
                for i in range(start_index, search_limit + 1):
                    if event_pairs[i] == seq[0]:
                        matched_events.append(self.events[i])
                        first_event_found_at = i
                        break
                else:
                    break

                seq_idx = 1
                for i in range(first_event_found_at + 1, n_events):
                    if (n_events - i) < (seq_len - seq_idx):
                        break

                    if seq_idx < seq_len and event_pairs[i] == seq[seq_idx]:
                        matched_events.append(self.events[i])
                        seq_idx += 1

                if len(matched_events) == seq_len:
                    sequences.append(matched_events)
                    if not repeat:
                        return sequences
                start_index = first_event_found_at + 1

        return sequences
