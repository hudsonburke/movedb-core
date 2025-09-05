from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON
from datetime import datetime
from typing import Any, TYPE_CHECKING, Optional
import polars as pl
from .hierarchy import TrialSubjectLink
from .groups import TrialGroupLink

if TYPE_CHECKING:
    from .events import Event
    from .markers import Marker
    from .analogs import Analog
    from .forceplates import ForcePlate
    from .hierarchy import CaptureSession, Subject
    from .groups import TrialGroup

class Trial(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="", index=True)

    capture_session_id: int | None = Field(default=None, foreign_key="capturesession.id")
    capture_session: Optional["CaptureSession"] = Relationship(back_populates="trials")
    subjects: list["Subject"] = Relationship(back_populates="trials", link_model=TrialSubjectLink)
    groups: list["TrialGroup"] = Relationship(back_populates="trials", link_model=TrialGroupLink)
    timestamp: datetime | None = None
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    events: list["Event"] = Relationship(back_populates="trial")

    markers: list["Marker"] = Relationship(back_populates="trial")
    analogs: list["Analog"] = Relationship(back_populates="trial")
    forceplates: list["ForcePlate"] = Relationship(back_populates="trial")

    def __init__(self, **data):
        super().__init__(**data)
        # Private cache storage - excluded from database
        self._marker_cache: dict[str, "Marker"] = {}
        self._analog_cache: dict[str, "Analog"] = {}
        self._forceplate_cache: dict[str, "ForcePlate"] = {}

    def __setattr__(self, name: str, value: Any) -> None:
        # Clear specific cache when corresponding attribute changes
        if name == "markers":
            self._marker_cache = {}
        elif name == "analogs":
            self._analog_cache = {}
        elif name == "forceplates":
            self._forceplate_cache = {}
        super().__setattr__(name, value)

    def get_marker(self, name: str) -> Optional["Marker"]:
        if not self._marker_cache:
            self._marker_cache = {marker.name: marker for marker in self.markers}
        return self._marker_cache.get(name)

    def get_analog(self, name: str) -> Optional["Analog"]:
        if not self._analog_cache:
            self._analog_cache = {analog.name: analog for analog in self.analogs}
        return self._analog_cache.get(name)

    def get_forceplate(self, name: str) -> Optional["ForcePlate"]:
        if not self._forceplate_cache:
            self._forceplate_cache = {fp.name: fp for fp in self.forceplates}
        return self._forceplate_cache.get(name)

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

    def get_event_sequences(self, seq: list[tuple[str, str]], repeat: bool = False, strict: bool = False) -> list[list["Event"]]:
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

    def markers_to_dataframe(self) -> pl.DataFrame:
        """
        Convert all trial markers to a combined polars DataFrame.
        
        Returns:
            pl.DataFrame: Combined dataframe with columns:
                - timestamp: timedelta timestamps
                - marker_name: string marker identifier
                - x, y, z: spatial coordinates (float)
                - residual: marker reconstruction residual (float)
        """
        if not self.markers:
            return pl.DataFrame(schema={
                "timestamp": pl.Duration,
                "marker_name": pl.String,
                "x": pl.Float64,
                "y": pl.Float64, 
                "z": pl.Float64,
                "residual": pl.Float64
            })
        
        marker_dfs = []
        for marker in self.markers:
            df = marker.to_polars.with_columns(
                pl.lit(marker.name).alias("marker_name")
            ).select([
                "timestamp", "marker_name", "x", "y", "z", "residual"
            ])
            marker_dfs.append(df)
        
        return pl.concat(marker_dfs, how="vertical")

    def analogs_to_dataframe(self) -> pl.DataFrame:
        """
        Convert all trial analogs to a combined polars DataFrame.
        
        Returns:
            pl.DataFrame: Combined dataframe with columns:
                - timestamp: timedelta timestamps
                - analog_name: string analog identifier  
                - value: scaled analog value (float)
        """
        if not self.analogs:
            return pl.DataFrame(schema={
                "timestamp": pl.Duration,
                "analog_name": pl.String,
                "value": pl.Float64
            })
        
        analog_dfs = []
        for analog in self.analogs:
            df = analog.to_polars.with_columns(
                pl.lit(analog.name).alias("analog_name")
            ).select([
                "timestamp", "analog_name", "value"
            ])
            analog_dfs.append(df)
        
        return pl.concat(analog_dfs, how="vertical")

    def forceplates_to_dataframe(self) -> pl.DataFrame:
        """
        Convert all trial force plates to a combined polars DataFrame.
        
        Returns:
            pl.DataFrame: Combined dataframe with columns:
                - timestamp: timedelta timestamps
                - forceplate_name: string forceplate identifier
                - force_x, force_y, force_z: force components (float)
                - moment_x, moment_y, moment_z: moment components (float)
                - cop_x, cop_y, cop_z: center of pressure coordinates (float)
                - freemoment_x, freemoment_y, freemoment_z: free moment components (float)
        """
        if not self.forceplates:
            return pl.DataFrame(schema={
                "timestamp": pl.Duration,
                "forceplate_name": pl.String,
                "force_x": pl.Float64,
                "force_y": pl.Float64,
                "force_z": pl.Float64,
                "moment_x": pl.Float64,
                "moment_y": pl.Float64,
                "moment_z": pl.Float64,
                "cop_x": pl.Float64,
                "cop_y": pl.Float64,
                "cop_z": pl.Float64,
                "freemoment_x": pl.Float64,
                "freemoment_y": pl.Float64,
                "freemoment_z": pl.Float64
            })
        
        forceplate_dfs = []
        for forceplate in self.forceplates:
            df = forceplate.to_polars.with_columns(
                pl.lit(forceplate.name).alias("forceplate_name")
            ).select([
                "timestamp", "forceplate_name", 
                "force_x", "force_y", "force_z",
                "moment_x", "moment_y", "moment_z",
                "cop_x", "cop_y", "cop_z",
                "freemoment_x", "freemoment_y", "freemoment_z"
            ])
            forceplate_dfs.append(df)
        
        return pl.concat(forceplate_dfs, how="vertical")
