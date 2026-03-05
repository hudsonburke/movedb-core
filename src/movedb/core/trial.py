"""Trial data structure for biomechanical trial data."""

from pydantic import BaseModel, Field

from .events import Event
from .markers import MarkerData
from .analogs import AnalogData
from .forceplates import ForceplateData


class TrialData(BaseModel):
    """
    Complete data for a single biomechanical trial.

    Composes signal data (markers, analogs, forceplates) with
    event annotations and lightweight metadata. Contains no
    database or storage references — purely in-memory data.
    """

    name: str = Field(description="Trial name (e.g., 'Walk_01')")
    trial_type: str = Field(
        default="",
        description="Type of trial (e.g., 'static', 'walking', 'running')",
    )

    # Signal data
    markers: MarkerData | None = Field(default=None, description="Marker trajectory data")
    analogs: AnalogData | None = Field(default=None, description="Analog channel data")
    forceplates: dict[str, ForceplateData] = Field(
        default_factory=dict,
        description="Force plate data keyed by plate name",
    )

    # Events
    events: list[Event] = Field(
        default_factory=list,
        description="Discrete events within the trial",
    )

    def get_events(self, label: str = "", context: str = "") -> list[Event]:
        """
        Return events filtered by label and/or context.

        Args:
            label: Filter by event label. Empty string matches all.
            context: Filter by event context. Empty string matches all.

        Returns:
            List of matching Event instances.
        """
        return [
            event
            for event in self.events
            if (not label or event.label == label)
            and (not context or event.context == context)
        ]

    def get_event_sequences(
        self, seq: list[tuple[str, str]], repeat: bool = False, strict: bool = False
    ) -> list[list[Event]]:
        """
        Find sequences of events matching a pattern of (context, label) tuples.

        Args:
            seq: List of (context, label) tuples defining the sequence pattern.
                 Example: [("Left", "Foot Strike"), ("Left", "Foot Off")]
            repeat: If True, find all occurrences. If False, only the first.
            strict: If True, events must be consecutive (no intervening events).
                    If False, other events may appear between sequence elements.

        Returns:
            List of matched sequences, where each sequence is a list of Events.
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
