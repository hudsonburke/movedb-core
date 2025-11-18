from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON
from datetime import datetime
from typing import Any, TYPE_CHECKING, Optional, Dict, List
import numpy as np
from pathlib import Path
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
    capture_session_id: int | None = Field(default=None, foreign_key="capturesession.id")
    capture_session: Optional["CaptureSession"] = Relationship(back_populates="trials")
    subjects: list["Subject"] = Relationship(back_populates="trials", link_model=TrialSubjectLink)
    groups: list["TrialGroup"] = Relationship(back_populates="trials", link_model=TrialGroupLink)
    
    timestamp: datetime | None = None
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # HDF5 storage reference
    hdf5_path: str | None = Field(default=None, index=True)
    
    # Cached metadata about trial contents (avoids opening HDF5 for simple queries)
    marker_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    analog_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    forceplate_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    marker_rate: float | None = None
    analog_rate: float | None = None
    forceplate_rate: float | None = None
    
    n_frames: int | None = None
    first_frame: int = 0
    last_frame: int | None = None
    
    # Event data (lightweight, keep in SQL)
    events: list["Event"] = Relationship(back_populates="trial")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Auto-generate HDF5 path if ID is provided and path doesn't exist
        if self.id and not self.hdf5_path:
            from ..storage import get_storage_config, get_trial_hdf5_path
            config = get_storage_config()
            self.hdf5_path = str(get_trial_hdf5_path(self.id, config.hdf5_base_dir))
    
    # ===== Data Access Methods =====
    
    def load_markers(self) -> Dict[str, Any]:
        """
        Load marker data from HDF5.
        
        Returns:
            Dict with 'data' (n_frames, n_markers, 3), 'marker_names', 'rate', etc.
        """
        if not self.hdf5_path or self.id is None:
            raise ValueError("Trial has no HDF5 path or ID")
        
        from ..storage import HDF5TrialStorage
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return storage.read_markers()
    
    def get_marker(self, marker_name: str) -> Optional[np.ndarray]:
        """
        Get data for a specific marker.
        
        Args:
            marker_name: Marker name
            
        Returns:
            Array of shape (n_frames, 3) or None if not found
        """
        if not self.hdf5_path or self.id is None:
            return None
        
        from ..storage import HDF5TrialStorage
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return storage.get_marker_by_name(marker_name)
    
    def load_analogs(self) -> Dict[str, Any]:
        """Load analog data from HDF5."""
        if not self.hdf5_path or self.id is None:
            raise ValueError("Trial has no HDF5 path or ID")
        
        from ..storage import HDF5TrialStorage
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return storage.read_analogs()
    
    def load_forceplate(self, name: str) -> Dict[str, Any]:
        """Load force plate data from HDF5."""
        if not self.hdf5_path or self.id is None:
            raise ValueError("Trial has no HDF5 path or ID")
        
        from ..storage import HDF5TrialStorage
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return storage.read_forceplate(name)
    
    def load_all_forceplates(self) -> Dict[str, Dict[str, Any]]:
        """Load all force plate data."""
        if not self.hdf5_path or self.id is None:
            return {}
        
        from ..storage import HDF5TrialStorage
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return {
                name: storage.read_forceplate(name)
                for name in storage.list_forceplates()
            }
    
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
        self, 
        seq: list[tuple[str, str]], 
        repeat: bool = False, 
        strict: bool = False
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
    
    # ===== OpenSim Export Methods =====
    
    def export_to_trc(
        self,
        filepath: str,
        output_units: str | None = None,
        rotation: np.ndarray = np.eye(3),
    ) -> None:
        """
        Export marker data to OpenSim TRC format.
        
        Args:
            filepath: Output TRC file path
            output_units: Optional output units (will convert if different from source)
            rotation: Optional rotation matrix to apply to coordinates
        """
        from ..osim import export_trc
        
        if self.hdf5_path is None:
            raise ValueError(
                f"Trial {self.id} ('{self.name}') has no HDF5 data. "
                f"Ensure trial was ingested with HDF5 storage enabled."
            )
        
        # Load markers from HDF5
        marker_data_dict = self.load_markers()
        
        # Extract data
        markers_array = marker_data_dict['data']  # Shape: (n_frames, n_markers, 3)
        marker_names = marker_data_dict['marker_names']
        rate = marker_data_dict['rate']
        units = marker_data_dict['units']
        
        # Convert to dict format expected by export_trc
        markers = {}
        for i, name in enumerate(marker_names):
            # Extract marker data: (n_frames, 3)
            marker_xyz = markers_array[:, i, :]
            # Replace sentinel values with NaN
            marker_xyz = np.where(marker_xyz == -9999.0, np.nan, marker_xyz)
            markers[name] = marker_xyz
        
        # Generate time array
        n_frames = markers_array.shape[0]
        time = np.arange(n_frames) / rate
        
        # Export using low-level function
        export_trc(
            filepath=filepath,
            markers=markers,
            time=time,
            rate=rate,
            units=units,
            output_units=output_units,
            rotation=rotation
        )
    
    def export_forceplates_to_mot(
        self,
        filepath: str,
        metadata: dict[str, Any] = {},
        rotation: np.ndarray = np.eye(3),
    ) -> None:
        """
        Export force plate data to OpenSim MOT format.
        
        Args:
            filepath: Output MOT file path
            metadata: Optional metadata to include in MOT file
            rotation: Optional rotation matrix to apply to force/moment/cop vectors
        """
        import polars as pl
        from ..osim import export_mot
        
        if self.hdf5_path is None:
            raise ValueError(
                f"Trial {self.id} ('{self.name}') has no HDF5 data. "
                f"Ensure trial was ingested with HDF5 storage enabled."
            )
        
        if not self.forceplate_names:
            raise ValueError(f"Trial {self.id} ('{self.name}') has no force plates")
        
        # Load all force plates
        all_fp_data = self.load_all_forceplates()
        
        # Get first force plate to determine number of frames
        first_fp = all_fp_data[self.forceplate_names[0]]
        n_frames = first_fp['forces'].shape[0]
        rate = first_fp['rate']
        
        # Generate time column
        time = np.arange(n_frames) / rate
        
        # Build data dict
        data_dict = {"time": time}
        
        for fp_name in self.forceplate_names:
            fp_data = all_fp_data[fp_name]
            forces = fp_data['forces']  # (n_frames, 3)
            moments = fp_data['moments']  # (n_frames, 3)
            cop = fp_data['cop']  # (n_frames, 3)
            
            # Apply rotation if provided
            if not np.allclose(rotation, np.eye(3)):
                forces = (rotation @ forces.T).T
                moments = (rotation @ moments.T).T
                cop = (rotation @ cop.T).T
            
            # Add to data dict with force plate prefix
            prefix = fp_name.replace(" ", "_")
            data_dict[f"{prefix}_force_vx"] = forces[:, 0]
            data_dict[f"{prefix}_force_vy"] = forces[:, 1]
            data_dict[f"{prefix}_force_vz"] = forces[:, 2]
            data_dict[f"{prefix}_moment_x"] = moments[:, 0]
            data_dict[f"{prefix}_moment_y"] = moments[:, 1]
            data_dict[f"{prefix}_moment_z"] = moments[:, 2]
            data_dict[f"{prefix}_force_px"] = cop[:, 0]
            data_dict[f"{prefix}_force_py"] = cop[:, 1]
            data_dict[f"{prefix}_force_pz"] = cop[:, 2]
        
        # Create polars DataFrame
        df = pl.DataFrame(data_dict)
        
        # Export using low-level function
        export_mot(filepath=filepath, data=df, metadata=metadata, nans_as_zero=True)
