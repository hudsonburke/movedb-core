from .events import Event
from .markers import Marker
from .analogs import Analog
from .hierarchy import CaptureSession
from .forceplates import ForcePlate
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Any

class Trial(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="", index=True)
    session_id: int | None = Field(default=None, foreign_key="session.id")
    session: CaptureSession = Relationship(back_populates="trials")
    start_timestamp: datetime | None = Field(default_factory=datetime.now)

    events: list[Event] = Relationship(back_populates="trial")

    markers: list[Marker] = Relationship(back_populates="trial")
    analogs: list[Analog] = Relationship(back_populates="trial")
    forceplates: list[ForcePlate] = Relationship(back_populates="trial")

    # Private cache storage - excluded from database
    _marker_cache: dict[str, Marker] = Field(default_factory=dict, exclude=True)
    _analog_cache: dict[str, Analog] = Field(default_factory=dict, exclude=True)
    _forceplate_cache: dict[str, ForcePlate] = Field(default_factory=dict, exclude=True)

    def __setattr__(self, name: str, value: Any) -> None:
        # Clear specific cache when corresponding attribute changes
        if name == "markers":
            self._marker_cache = {}
        elif name == "analogs":
            self._analog_cache = {}
        elif name == "forceplates":
            self._forceplate_cache = {}
        super().__setattr__(name, value)

    def get_marker(self, name: str) -> Marker | None:
        if not self._marker_cache:
            self._marker_cache = {marker.name: marker for marker in self.markers}
        return self._marker_cache.get(name)

    def get_analog(self, name: str) -> Analog | None:
        if not self._analog_cache:
            self._analog_cache = {analog.name: analog for analog in self.analogs}
        return self._analog_cache.get(name)

    def get_forceplate(self, name: str) -> ForcePlate | None:
        if not self._forceplate_cache:
            self._forceplate_cache = {fp.name: fp for fp in self.forceplates}
        return self._forceplate_cache.get(name)

    def get_events(self, label: str = "", context: str = "") -> list[Event]:
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

    def get_event_sequences(self, seq: list[tuple[str, str]], repeat: bool = False, strict: bool = False) -> list[list[Event]]:
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
            # For strict mode, check consecutive sequences
            for start in range(n_events - seq_len + 1):
                if event_pairs[start:start + seq_len] == seq:
                    matched_events = self.events[start:start + seq_len]
                    sequences.append(matched_events)
                    if not repeat:
                        break
        else:
            search_limit = n_events - seq_len
            start_index = 0
            while start_index <= search_limit:
                matched_events = []
                first_event_found_at = -1
                for i in range(start_index, search_limit+1):
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
