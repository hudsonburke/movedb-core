import os
import pickle
from loguru import logger
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
        event_sequence = [(event.context, event.label) for event in self.events]
        
        if strict:
            # For strict mode, check consecutive sequences
            for start in range(len(event_sequence) - len(seq) + 1):
                if event_sequence[start:start + len(seq)] == seq:
                    matched_events = self.events[start:start + len(seq)]
                    sequences.append(matched_events)
                    if not repeat:
                        break
        else:
            # For non-strict mode, allow gaps between sequence elements
            for start in range(len(event_sequence)):
                matched_events = []
                seq_idx = 0
                
                for i in range(start, len(event_sequence)):
                    if seq_idx >= len(seq):
                        break
                    
                    if event_sequence[i] == seq[seq_idx]:
                        matched_events.append(self.events[i])
                        seq_idx += 1
                
                if seq_idx == len(seq):  # Found complete sequence
                    sequences.append(matched_events)
                    if not repeat:
                        break

        return sequences

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
