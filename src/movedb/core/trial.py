"""
Refactored Trial class with improved separation of concerns.
"""

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

    def link_file(self, file_key: str, file_path: str):
        """Link a file to this trial by storing its absolute path."""
        self.linked_files[file_key] = os.path.abspath(file_path)

    def get_linked_file(self, file_key: str) -> str:
        """
        Get the absolute path of an associated file by its key.
        Returns an empty string if the file is not associated.
        """
        return self.linked_files.get(file_key, "")

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
        If already computed, return the cached result.
        """

        if self.point_gaps:
            # Check for markers and regions already computed
            relevant_gaps = {}
            for marker, gap_list in self.point_gaps.items():
                if marker not in relevant_gaps:
                    relevant_gaps[marker] = []
                relevant_gaps[marker].extend(gap_list)
            return relevant_gaps

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
            for marker in marker_names:
                if marker not in self.points.trajectories:
                    gaps[marker] = [(start, end)]
                    continue
                marker_data = self.points.trajectories[marker].data
                # Check if marker data exists in every frame in the region
                region_data = marker_data[start : end + 1]
                for coord in ["x", "y", "z"]:
                    missing_data = region_data.filter(pl.col(coord).is_null())
                    if not missing_data.is_empty():
                        if marker not in gaps:
                            gaps[marker] = []
                        gaps[marker].append((start, end))
                        break
        return gaps

    @model_validator(mode="after")
    def _cache_point_gaps(self) -> "Trial":
        """Cache point gaps on initialization."""
        self.point_gaps = self.check_point_gaps()
        return self

    def find_full_frames(self, marker_names: list[str] | None = None) -> list[int]:
        """
        Find all frames where all specified markers have data.
        If no markers are specified, checks all markers.
        Returns a list of frame indices.
        """
        if marker_names is None:
            marker_names = list(self.points.trajectories.keys())
        full_frames = set(range(self.points.first_frame, self.points.last_frame + 1))
        for marker in marker_names:
            if marker not in self.points.trajectories:
                return []
            marker_data = self.points.trajectories[marker].data
            marker_full_frames = set(
                marker_data.filter(
                    (pl.col("x").is_not_null())
                    & (pl.col("y").is_not_null())
                    & (pl.col("z").is_not_null())
                )
                .select(pl.arange(0, marker_data.height))
                .to_series()
                .to_list()
            )
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
                if isinstance(value, list):
                    parameters[key] = value[0] if len(value) == 1 else value
                else:
                    parameters[key] = value

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
        c3d = ezc3d.c3d(file_path)
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

    def to_trc(
        self, filepath: str, output_units: str = "mm", rotation: np.ndarray = np.eye(3)
    ):
        """Export marker data to TRC format. Convenience method."""
        from ..file_io import export_trc

        export_trc(
            filepath,
            markers=self.points.to_dict(include_residual=False),
            time=self.points.time,
            rate=self.points.rate,
            units=self.points.units,
            output_units=output_units,
            rotation=rotation,
        )
        self.link_file("trc", filepath)

    # TODO: figure out how to decouple from Trial class
    def export_force_platforms(
        self,
        output_dir: str,
        applied_bodies: dict[
            int, str
        ],  # Expects dict of {platform_index (1-based): body_name}
        force_expressed_in_body: str = "ground",
        point_expressed_in_body: str = "ground",
        force_identifier: str = r"force%d_v",
        point_identifier: str = r"force%d_p",
        torque_identifier: str = r"moment%d_",
        rotation: np.ndarray = np.eye(3),
        mot_filename: str | None = None,
        external_loads_filename: str | None = None,
        unit_force: str = "N",
        unit_position: str = "m",
        unit_moment: str = "Nm",
        metadata: dict[str, Any] = {},
    ):
        """
        Export force plate metadata to OpenSim ExternalLoads .xml file and the data to a .mot file.

        For now, extract foot contact from .enf files, but in the future use contact
        """
        import opensim as osim

        from ..file_io import get_units_conversion_factor

        ext_loads = osim.ExternalLoads()

        if external_loads_filename is None:
            external_loads_filename = f"{self.name}_fp_setup.xml"
        external_loads_filepath = os.path.join(output_dir, external_loads_filename)

        if mot_filename is None:
            mot_filename = f"{self.name}_FP.mot"
        mot_filepath = os.path.join(output_dir, mot_filename)
        mot_labels = []
        mot_table = osim.TimeSeriesTable()
        time_col = self.analogs.time

        data = np.zeros(
            (len(self.force_platforms) * 9, len(time_col))
        )  # 3 forces, 3 moments, 3 center of pressure
        for i, fp in enumerate(self.force_platforms):
            display_i = i + 1  # For display purposes, OpenSim uses 1-based indexing
            fp_force_identifier = force_identifier % (display_i)
            fp_point_identifier = point_identifier % (display_i)
            fp_torque_identifier = torque_identifier % (display_i)
            mot_labels.extend([fp_force_identifier + coord for coord in "xyz"])
            mot_labels.extend(
                [fp_point_identifier + coord for coord in "xyz"]
            )  # This could be precomputed, but having it next to the data makes it clear what order it should be added
            mot_labels.extend([fp_torque_identifier + coord for coord in "xyz"])
            if display_i not in applied_bodies:
                warnings.warn(
                    f"Force platform {display_i} does not have an applied body defined. Skipping."
                )
                continue
            # Create ExternalForce for each force platform
            ext_force = osim.ExternalForce()
            ext_force.setName(f"FP{str(display_i)}")
            ext_force.setAppliedToBodyName(applied_bodies[display_i])

            ext_force.setForceExpressedInBodyName(force_expressed_in_body)
            ext_force.setForceIdentifier(fp_force_identifier)

            ext_force.setPointExpressedInBodyName(point_expressed_in_body)
            ext_force.setPointIdentifier(fp_point_identifier)

            ext_force.setTorqueIdentifier(fp_torque_identifier)

            ext_force.set_data_source_name(mot_filename)

            ext_loads.cloneAndAppend(ext_force)

            # Determine conversion factors for units
            (
                force_conversion_factor,
                position_conversion_factor,
                moment_conversion_factor,
            ) = (1.0, 1.0, 1.0)
            if fp.unit_force != unit_force:
                warnings.warn(
                    f"Force platform {display_i} force unit {fp.unit_force} "
                    f"does not match output unit {unit_force}. Converting forces."
                )
                force_conversion_factor = get_units_conversion_factor(
                    fp.unit_force, unit_force
                )
            if fp.unit_position != unit_position:
                warnings.warn(
                    f"Force platform {display_i} position unit {fp.unit_position} "
                    f"does not match output unit {unit_position}. Converting positions."
                )
                position_conversion_factor = get_units_conversion_factor(
                    fp.unit_position, unit_position
                )
            if fp.unit_moment != unit_moment:
                warnings.warn(
                    f"Force platform {display_i} torque unit {fp.unit_moment} "
                    f"does not match output unit {unit_moment}. Converting torques."
                )
                moment_conversion_factor = get_units_conversion_factor(
                    fp.unit_moment, unit_moment
                )

            # Rotate the force platform data
            force = (
                np.array(rotation @ np.array(fp.force).T).T
                * force_conversion_factor
                * -1.0
            )  # OpenSim expects forces to be in the opposite direction
            cop = (
                np.array(rotation @ np.array(fp.center_of_pressure).T).T
                * position_conversion_factor
            )
            free_moment = (
                np.array(rotation @ np.array(fp.free_moment).T).T
                * moment_conversion_factor
                * -1.0
            )  # OpenSim expects moments to be in the opposite direction

            data[i * 9 : i * 9 + 3, :] = force.T  # 3 forces
            data[i * 9 + 3 : i * 9 + 6, :] = cop.T  # 3 center of pressure
            data[i * 9 + 6 : i * 9 + 9, :] = free_moment.T  # 3 moments

        for i in range(len(time_col)):
            mot_table.appendRow(time_col[i], osim.RowVector(data[:, i]))

        mot_table.setColumnLabels(mot_labels)

        for key, value in metadata.items():
            mot_table.addTableMetaDataString(key, str(value))

        if "nRows" not in metadata:
            n_frames = self.force_platforms[
                0
            ].data.height  # Assuming all platforms have the same number of frames
            mot_table.addTableMetaDataString("nRows", str(n_frames))
        if "nColumns" not in metadata:
            n_columns = (
                len(self.force_platforms) * 9
            )  # 3 forces, 3 moments, 3 center of pressure
            mot_table.addTableMetaDataString("nColumns", str(n_columns))
        adapter = osim.STOFileAdapter()
        adapter.write(mot_table, mot_filepath)
        self.link_file("fp_mot", mot_filepath)
        ext_loads.setDataFileName(mot_filename)
        ext_loads.printToXML(external_loads_filepath)
        self.link_file("fp_setup", external_loads_filepath)

    def run_opensim_ik(self, model_path: str, **kwargs):
        """Run OpenSim Inverse Kinematics. Convenience method."""
        from ..file_io import opensim_ik

        ik_results_path, ik_setup_path = opensim_ik(self.name, model_path, **kwargs)
        self.link_file("ik_results", ik_results_path)
        self.link_file("ik_setup", ik_setup_path)

    def run_opensim_id(self, model_path: str, **kwargs):
        """Run OpenSim Inverse Dynamics. Convenience method."""
        from ..file_io import opensim_id

        id_results_path, id_setup_path = opensim_id(self.name, model_path, **kwargs)
        self.link_file("id_results", id_results_path)
        self.link_file("id_setup", id_setup_path)

    # TODO: These are definitely not the best implementations, but they work for now
    def get_stance_phases(
        self,
        side: str,
        foot_strike_label: str = "Foot Strike",
        foot_off_label: str = "Foot Off",
    ) -> list[tuple[Event, Event]]:
        """
        Get the stance phase for a specific side.
        Stance phase is defined as the time between foot strike and foot off events for that side.
        """
        stance_phases = []
        foot_strike = None
        foot_off = None
        for event in self.events:
            if event.context == side:
                if event.label == foot_strike_label:
                    foot_strike = event
                elif event.label == foot_off_label and foot_strike:
                    foot_off = event
            if foot_strike and foot_off:
                stance_phases.append((foot_strike, foot_off))
                foot_strike = None
                foot_off = None
        return stance_phases

    def get_swing_phases(
        self,
        side: str,
        foot_off_label: str = "Foot Off",
        foot_strike_label: str = "Foot Strike",
    ) -> list[tuple[Event, Event]]:
        """
        Get the swing phase for a specific side.
        Swing phase is defined as the time between foot off and next foot strike events for that side.
        """
        swing_phases = []
        foot_off = None
        next_foot_strike = None
        for event in self.events:
            if event.context == side:
                if event.label == foot_off_label:
                    foot_off = event
                elif event.label == foot_strike_label and foot_off:
                    next_foot_strike = event
            if foot_off and next_foot_strike:
                swing_phases.append((foot_off, next_foot_strike))
                foot_off = None
                next_foot_strike = None
        return swing_phases

    def get_stance_swing_phases(
        self,
        side: str,
        foot_strike_label: str = "Foot Strike",
        foot_off_label: str = "Foot Off",
    ) -> list[tuple[Event, Event, Event]]:
        """
        Get the coupled stance and swing phases for a specific side.
        Each tuple contains (foot strike, foot off, next foot strike).
        """
        stance_swing_phases = []
        foot_strike = None
        foot_off = None
        next_foot_strike = None
        for event in self.events:
            if event.context == side:
                if event.label == foot_strike_label and not foot_strike:
                    foot_strike = event
                elif event.label == foot_off_label and foot_strike:
                    foot_off = event
                elif event.label == foot_strike_label and foot_off:
                    next_foot_strike = event
            if foot_strike and foot_off and next_foot_strike:
                stance_swing_phases.append((foot_strike, foot_off, next_foot_strike))
                foot_strike = next_foot_strike
                foot_off = None
                next_foot_strike = None
        return stance_swing_phases
