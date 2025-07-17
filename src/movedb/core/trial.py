import os
import pickle
import warnings
from typing import Any, Type, TypeVar

import ezc3d
import numpy as np
import polars as pl
from pydantic import BaseModel, model_validator

from movedb.utils.ezc3d_helpers import get_c3d_param

from .events import Event
from .force_platforms import EZForcePlatform
from .time_series import Analogs, Points

# from sqlmodel import SQLModel, Field, Relationship, SQLModel, JSON, Column

# Define a TypeVar that is bound by the Trial class itself
_T = TypeVar("_T", bound="Trial")


class TrialBase(BaseModel):
    """Base trial class that can be extended by database models."""

    name: str
    session_name: str = ""
    subject_names: list[str] | str = ""
    classification: str = ""


class Trial(TrialBase):

    # Trial Metadata
    name: str
    session_name: str = ""
    subject_names: list[str] | str = ""
    classification: str = ""
    linked_files: dict[str, str] = (
        {}
    )  # Map of associated files, e.g. C3D file path, etc.
    parameters: dict[str, Any] = {}

    events: list[Event] = []  # Should be in ascending order by frame or time

    points: Points
    point_gaps: dict[str, list[tuple[int, int]]] = {}

    analogs: Analogs
    force_platforms: list[EZForcePlatform] = []  # List of force platforms, if any

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
        
    @model_validator(mode="after")
    def order_events(self) -> "Trial":
        """
        Ensure events are in ascending order by frame or time.
        """
        self.events = sorted(
            self.events,
            key=lambda e: (e.get_frame(self.points.rate), e.get_time(self.points.rate)),
        )
        return self

    def get_event_sequences(self, seq: list[tuple[str, str]], repeat: bool = False, strict: bool = False) -> list[list[Event]]:
        """
        Get sequences of events based on a list of (label, context) tuples.
        
        Args:
            seq: A list of (label, context) tuples defining the event sequence to find.
            repeat: If True, find all occurrences of the sequence, including overlapping ones. 
                   If False, only find the first complete occurrence.
            strict: If True, only match sequences where events appear consecutively without interruptions.
                   If False, allow other events between sequence elements.
                   
        Returns:
            A list of event sequences, where each sequence is a list of Event objects.
            If repeat=False, the list will contain at most one sequence.
        """
        if not seq:
            return []
            
        sequences = []
        
        # If not in repeat mode, just find the first occurrence
        if not repeat:
            current_sequence = []
            seq_index = 0
            
            for event in self.events:
                if (event.label, event.context) == seq[seq_index]:
                    current_sequence.append(event)
                    seq_index += 1
                    
                    # If we've completed the sequence
                    if seq_index >= len(seq):
                        sequences.append(current_sequence)
                        break
                elif strict and seq_index > 0:
                    # In strict mode, reset sequence if we encounter a non-matching event
                    current_sequence = []
                    seq_index = 0
                    
                    # Check if this event could start a new sequence
                    if (event.label, event.context) == seq[0]:
                        current_sequence.append(event)
                        seq_index = 1
            
            # Warn if we didn't find a complete sequence
            if not sequences:
                warnings.warn(
                    f"No complete event sequence matching {seq} was found in trial {self.name}."
                )
                
            return sequences
        
        # In repeat mode, find all occurrences (including overlapping ones)
        # by starting a search from each event
        for start_idx in range(len(self.events)):
            current_sequence = []
            seq_index = 0
            event_idx = start_idx
            
            while event_idx < len(self.events):
                event = self.events[event_idx]
                
                if (event.label, event.context) == seq[seq_index]:
                    current_sequence.append(event)
                    seq_index += 1
                    
                    # If we've completed a sequence
                    if seq_index >= len(seq):
                        sequences.append(list(current_sequence))  # Make a copy
                        break
                        
                elif strict and seq_index > 0:
                    # In strict mode, a non-matching event breaks the sequence
                    break
                
                event_idx += 1
        
        # If we didn't find any complete sequences
        if not sequences:
            warnings.warn(
                f"No complete event sequences matching {seq} were found in trial {self.name}."
            )
            
        return sequences

    def check_point_gaps(
        self,
        marker_names: list[str] | None = None,
        regions: list[tuple[int, int] | tuple[float, float]] | None = None,
    ) -> dict[str, list[tuple[int, int]]]:
        """
        Check for gaps in point data for specified markers and regions.
        A gap is defined as any frame in the region where the marker data is missing (NaN).
        Returns a dictionary with marker names as keys and lists of (start, end) tuples indicating integer frame gaps.

        If no markers or regions are specified, checks all markers and the entire trial duration.
        If already computed and no specific markers/regions requested, return the cached result.
        """

        # Only use cached result if no specific markers or regions are requested
        if (self.point_gaps and 
            marker_names is None and 
            regions is None):
            return self.point_gaps.copy()

        gaps = {}
        if marker_names is None:
            marker_names = list(self.points.trajectories.keys())
        if regions is None:
            regions = [(self.points.first_frame, self.points.last_frame)]

        for region in regions:
            start, end = region
            if isinstance(start, float):
                start = int(start * self.points.rate)
            if isinstance(end, float):
                end = int(end * self.points.rate)
            
            # Convert absolute frames to relative indices
            start_idx = start - self.points.first_frame
            end_idx = end - self.points.first_frame
            
            # Ensure indices are within bounds
            start_idx = max(0, start_idx)
            end_idx = min(self.points.total_frames - 1, end_idx)
            
            for marker in marker_names:
                if marker not in self.points.trajectories:
                    if marker not in gaps:
                        gaps[marker] = []
                    gaps[marker].append((start, end))
                    continue
                    
                marker_data = self.points.trajectories[marker].data
                
                # Find actual gap boundaries within the region
                gap_starts = []
                gap_ends = []
                in_gap = False
                
                for i in range(start_idx, end_idx + 1):
                    # Check if any coordinate is null or NaN at this frame
                    row = marker_data[i]
                    has_null = (row.select(pl.col("x").is_null()).item() or 
                               row.select(pl.col("y").is_null()).item() or 
                               row.select(pl.col("z").is_null()).item())
                    has_nan = (row.select(pl.col("x").is_nan()).item() or 
                              row.select(pl.col("y").is_nan()).item() or 
                              row.select(pl.col("z").is_nan()).item())
                    
                    if (has_null or has_nan) and not in_gap:
                        # Start of a gap
                        gap_starts.append(i + self.points.first_frame)
                        in_gap = True
                    elif not (has_null or has_nan) and in_gap:
                        # End of a gap
                        gap_ends.append(i + self.points.first_frame - 1)
                        in_gap = False
                
                # Handle case where gap extends to end of region
                if in_gap:
                    gap_ends.append(end)
                
                # Create gap tuples
                if gap_starts:
                    if marker not in gaps:
                        gaps[marker] = []
                    for gap_start, gap_end in zip(gap_starts, gap_ends):
                        gaps[marker].append((gap_start, gap_end))
        
        return gaps
    
    def find_full_frames(self, marker_names: list[str] | None = None) -> list[int]:
        """
        Find all frames where all specified markers have data.
        If no markers are specified, checks all markers.
        Returns a list of frame indices (absolute frame numbers).
        """
        if marker_names is None:
            marker_names = list(self.points.trajectories.keys())
        
        # Start with all possible frames
        full_frames = set(range(self.points.first_frame, self.points.last_frame + 1))
        
        for marker in marker_names:
            if marker not in self.points.trajectories:
                return []  # If any marker is missing, no frames can be full
            
            marker_data = self.points.trajectories[marker].data
            
            # Find frames where this marker has complete data
            marker_full_indices = []
            for i in range(marker_data.height):
                row = marker_data[i]
                has_complete_data = (not row.select(pl.col("x").is_null()).item() and 
                                   not row.select(pl.col("y").is_null()).item() and 
                                   not row.select(pl.col("z").is_null()).item() and
                                   not row.select(pl.col("x").is_nan()).item() and 
                                   not row.select(pl.col("y").is_nan()).item() and 
                                   not row.select(pl.col("z").is_nan()).item())
                if has_complete_data:
                    marker_full_indices.append(i + self.points.first_frame)
            
            marker_full_frames = set(marker_full_indices)
            full_frames &= marker_full_frames
            
        return sorted(full_frames)

    # Factory methods for creating Trial instances
    @classmethod
    def from_c3d(
        cls: Type[_T],
        c3d_object: ezc3d.c3d,
        trial_name: str = "",
        session_name: str = "",
        classification: str = "",
    ) -> _T:

        subject_names = get_c3d_param(
            c3d_object,
            "SUBJECTS",
            "NAMES",
            default=cls.model_fields["subject_names"].default,
        )
        parameters = {}
        if "PROCESSING" in c3d_object.parameters:
            for key, value in c3d_object.parameters["PROCESSING"].items():
                arr = value.get("value", [])
                if isinstance(arr, list) or isinstance(arr, np.ndarray):
                    parameters[key] = arr[0] if len(arr) == 1 else arr
                else:
                    parameters[key] = arr

        num_events = get_c3d_param(c3d_object, "EVENT", "USED", default=[0])[0]

        return cls(
            name=trial_name,
            session_name=session_name,
            classification=classification,
            subject_names=subject_names,
            points=Points.from_c3d(c3d_object),
            analogs=Analogs.from_c3d(c3d_object),
            force_platforms=[
                EZForcePlatform.from_c3d(c3d_object, index=i)
                for i in range(len(c3d_object.data["platform"]))
            ],
            parameters=parameters,
            events=[
                Event.from_c3d(c3d_object, index=i)
                for i in range(int(num_events))
            ],
        )

    @classmethod
    def from_c3d_file(
        cls: Type[_T],
        file_path: str,
        trial_name: str = "",
        session_name: str = "",
        classification: str = "",
    ) -> _T:
        """
        Create a Trial instance from a C3D file.
        """
        c3d = ezc3d.c3d(file_path, extract_forceplat_data=True)
        return cls.from_c3d(
            c3d,
            trial_name=trial_name,
            session_name=session_name,
            classification=classification,
        )

    def to_pkl(self, path: str):
        """
        Save the Trial to a pickle file.
        Args:
            path (str): Path to save the pickle file.
        """
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def from_pkl(cls: Type[_T], path: str) -> _T:
        """
        Load a Trial from a pickle file.
        Args:
            path (str): Path to the pickle file.
        Returns:
            Trial: The loaded Trial object.
        """
        with open(path, "rb") as f:
            data = pickle.load(f)
        if not isinstance(data, cls):
            raise ValueError(f"Loaded data is not an instance of {cls}: {type(data)}")
        return data

    @classmethod
    def from_vicon_nexus(cls) -> "Trial":
        """
        Create a Trial instance from an open trial in Vicon Nexus.
        This method requires the Vicon Nexus API to be installed and configured.
        https://pycgm2.readthedocs.io/en/latest/Pages/thirdParty/NexusAPI.html
        """
        raise NotImplementedError("Vicon Nexus API integration is not implemented yet.")

    def to_mat(self, filepath: str):
        """
        Export trial data to a .mat file.
        The structure of the .mat file will include:
        - Info: Metadata about the trial, including name, session, subjects, classification, camera rate, and subject parameters.
        - Events: A structure containing the total number of frames, region of interest, and lists of event frames for foot strikes, foot offs, and general events.
        - Markers: A dictionary of marker data, excluding residuals.
        - Analog: A dictionary of analog data, with keys modified to replace '.' with '_', and time as a separate list.
        Args:
            filepath (str): Path to save the .mat file.
        """
        import scipy.io as sio

        mat_dict = {}
        mat_dict["Info"] = {
            "TrialName": self.name,
            "Session": self.session_name,
            "Subjects": self.subject_names,
            "Classification": self.classification,
            "CameraRate": self.points.rate,
            "SubjectParameters": self.parameters,
        }

        mat_dict["Events"] = {
            "TotalFrames": self.points.last_frame + 1 - self.points.first_frame,
            "RegionOfInterest": [
                self.points.first_frame,
                self.points.last_frame,
            ],
            "LeftFootStrike": [
                event.get_frame(self.points.rate)
                for event in self.get_events(label="Foot Strike", context="Left")
            ],
            "RightFootStrike": [
                event.get_frame(self.points.rate)
                for event in self.get_events(label="Foot Strike", context="Right")
            ],
            "LeftFootOff": [
                event.get_frame(self.points.rate)
                for event in self.get_events(label="Foot Off", context="Left")
            ],
            "RightFootOff": [
                event.get_frame(self.points.rate)
                for event in self.get_events(label="Foot Off", context="Right")
            ],
            "General": [
                event.get_frame(self.points.rate)
                for event in self.get_events(context="General")
            ],
        }

        mat_dict["Markers"] = self.points.to_dict(include_residual=False)

        # Convert analog keys to replace '.' with '_'
        analog_dict = self.analogs.to_df().to_dict()
        analog_dict = {k.replace(".", "_"): v for k, v in analog_dict.items()}
        mat_dict["Analog"] = analog_dict
        mat_dict["Analog"]["Time"] = self.analogs.time.tolist()

        sio.savemat(filepath, mat_dict)
