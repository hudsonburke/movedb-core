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
    )  # TODO: Is this the right way to do optional relationships in SQLModel?
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
            # For strict mode, check consecutive sequences
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

    def create_opensim_external_forces(
        self,
        enf_path: str,
        body_mapping: dict[str, str] = {"Left": "foot_l", "Right": "foot_r"},
        force_expressed_in_body: str = "ground",
        point_expressed_in_body: str = "ground",
    ) -> list:
        """
        Create OpenSimExternalForce objects for forceplates based on ENF file.

        Convenience method that uses trial's forceplate names with ENF-based
        body assignment detection. For more control or alternative contact detection
        methods, use the standalone functions in movedb.osim.utils.

        Args:
            enf_path: Path to the .enf file associated with this trial
            body_mapping: Dictionary mapping ENF context names to OpenSim body names
            force_expressed_in_body: Body frame in which forces are expressed
            point_expressed_in_body: Body frame in which application points are expressed

        Returns:
            List of OpenSimExternalForce objects

        See Also:
            movedb.osim.utils.get_forceplate_body_mapping_from_enf
            movedb.osim.utils.create_opensim_external_forces
        """
        from ..osim.utils import (
            get_forceplate_body_mapping_from_enf,
            create_opensim_external_forces,
        )

        # Get forceplate-to-body mapping from ENF file
        fp_to_body = get_forceplate_body_mapping_from_enf(enf_path, body_mapping)

        # Create external forces using the standalone utility
        return create_opensim_external_forces(
            forceplate_names=self.forceplate_names,
            fp_to_body_mapping=fp_to_body,
            force_expressed_in_body=force_expressed_in_body,
            point_expressed_in_body=point_expressed_in_body,
        )

    def export_external_loads_for_id(
        self,
        enf_path: str,
        output_dir: str,
        body_mapping: dict[str, str] = {"Left": "foot_l", "Right": "foot_r"},
        mot_filename: str = "grf.mot",
        xml_filename: str = "external_loads.xml",
        rotation: np.ndarray = np.eye(3),
        metadata: dict[str, Any] = {},
    ) -> tuple[str, str]:
        """
        Export forceplate data and external loads configuration for OpenSim ID analysis.

        This method performs a complete export for inverse dynamics:
        1. Exports forceplate data to MOT file
        2. Parses ENF file to determine body assignments
        3. Creates and exports external loads XML file with proper body mappings

        Handles cases where multiple forceplates contact the same body.

        Args:
            enf_path: Path to the .enf file with forceplate-to-body assignments
            output_dir: Directory to write output files
            body_mapping: Mapping of ENF context names to OpenSim body names
            mot_filename: Name for the MOT file containing forceplate data
            xml_filename: Name for the XML file containing external loads configuration
            rotation: Rotation matrix to apply to force/moment/cop vectors
            metadata: Additional metadata for MOT file

        Returns:
            Tuple of (mot_filepath, xml_filepath)

        Example:
            >>> trial = Trial(name="Walk05")
            >>> mot_path, xml_path = trial.export_external_loads_for_id(
            ...     enf_path="Walk05.Trial.enf",
            ...     output_dir="id_results/",
            ...     body_mapping={'Left': 'foot_l', 'Right': 'foot_r'}
            ... )
            >>> # Creates:
            >>> # - id_results/grf.mot (forceplate data)
            >>> # - id_results/external_loads.xml (body assignments + MOT reference)
        """
        from pathlib import Path
        from loguru import logger
        from ..osim.io.write import export_external_loads

        # Create output directory if needed
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export forceplate data to MOT
        mot_filepath = str(output_path / mot_filename)
        logger.info(f"Exporting forceplate data to {mot_filepath}")
        self.export_forceplates_to_mot(
            filepath=mot_filepath, metadata=metadata, rotation=rotation
        )

        # Create external force objects based on ENF file
        logger.info(f"Reading forceplate-to-body assignments from {enf_path}")
        external_forces = self.create_opensim_external_forces(
            enf_path=enf_path, body_mapping=body_mapping
        )

        # Export external loads XML
        xml_filepath = str(output_path / xml_filename)
        logger.info(f"Exporting external loads configuration to {xml_filepath}")
        export_external_loads(
            filepath=xml_filepath,
            external_forces=external_forces,
            datafile_name=mot_filename,  # Relative path to MOT file
        )

        logger.success(
            f"Exported external loads for ID analysis:\n"
            f"  MOT file: {mot_filepath}\n"
            f"  XML file: {xml_filepath}\n"
            f"  Forceplates: {len(external_forces)} assigned to bodies"
        )

        return mot_filepath, xml_filepath
