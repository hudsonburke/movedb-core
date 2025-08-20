from .events import Event
from .markers import Marker
from .analogs import Analog
from .hierarchy import Session
from .forceplates import ForcePlate
from sqlmodel import SQLModel, Field, Relationship
from pydantic import model_validator
from datetime import datetime

class Trial(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="", index=True)
    session_id: int | None = Field(default=None, foreign_key="session.id")
    session: Session = Relationship(back_populates="trials")
    start_timestamp: datetime | None = Field(default_factory=datetime.now)
    # Map of associated files, e.g. C3D file path, etc.
    linked_files: dict[str, str] = {}

    events: list[Event] = Relationship(back_populates="trial")
    markers: list [Marker] = Relationship(back_populates="trial")
    analogs: list[Analog]= Relationship(back_populates="trial")
    forceplates: list[ForcePlate] = Relationship(back_populates="trial")

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
        
    @model_validator(mode="after") # TODO: Switch to SQL ordering methodology
    def order_events(self) -> "Trial":
        """
        Ensure events are in ascending order by frame or time.
        """
        self.events = sorted(
            self.events,
            key=lambda e: (e.get_frame(self.markers[0].rate), e.get_time(self.markers[0].rate)),
        )
        return self

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
