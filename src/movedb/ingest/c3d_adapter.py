import ezc3d
from datetime import datetime, timedelta
from typing import Any
import numpy as np
from ..models import (
    Event, 
    Trial,
    CaptureSession,
    Subject
)
from ..storage import HDF5TrialStorage, get_storage_config
from pydantic import BaseModel
from pathlib import Path

class C3DAdapter(BaseModel):
    """
    Adapter class for converting C3D file data to MoveDB models.
    Handles parameter access, error handling, and data conversion.
    """
    model_config = {"arbitrary_types_allowed": True}
    
    c3d: ezc3d.c3d
    
    @classmethod
    def from_file(cls, file_path: str, extract_forceplat_data: bool = True) -> "C3DAdapter":
        """Convenience method"""
        c3d_obj = ezc3d.c3d(file_path, extract_forceplat_data=extract_forceplat_data)
        return cls(c3d=c3d_obj)

    def get_param(self, *keys: str, index: int | None = None, default: Any = None) -> Any:
        """
        Get nested parameters from the C3D object.
        
        Args:
            *keys: Sequence of keys to access nested parameters
            index: Optional index for array parameters
            default: Default value if parameter not found
            
        Returns:
            Parameter value or default
            
        Raises:
            IndexError: If index is out of range for array parameters
        """
        param: dict = self.c3d.parameters
        for key in keys:
            param = param.get(key, {})
        value = param.get("value", default)
        
        if index is not None and (isinstance(value, list) or isinstance(value, np.ndarray)):
            if index < 0 or index >= len(value):
                raise IndexError(f"Index {index} out of range for parameter '{keys}'")
            return value[index]
        return value 

    def get_event(self, trial: Trial, index: int = 0) -> Event:
        """
        Extract event data from C3D file.

        Args:
            index: Index of the event to extract

        Returns:
            Event model instance

        Raises:
            ValueError: If EVENT parameters are missing or invalid
        """
        if "EVENT" not in self.c3d.parameters:
            raise ValueError("C3D object does not contain EVENT parameters")

        context = self.get_param("EVENT", "CONTEXTS", index=index, default="")
        label = self.get_param("EVENT", "LABELS", index=index, default="")

        # Get time in seconds from (min, sec) format
        times = self.get_param("EVENT", "TIMES", default=[[None, None]])
        if isinstance(times, np.ndarray):
            if times.ndim < 2 or times.shape[1] <= index:
                raise ValueError(f"No time data for event at index {index}")
            time_min, time_sec = times[:, index]
        else:
            # Handle list format
            if not times or len(times) < 2 or len(times[0]) <= index:
                raise ValueError(f"No time data for event at index {index}")
            time_min = times[0][index] if len(times[0]) > index else None
            time_sec = times[1][index] if len(times[1]) > index else None
        if time_min is None or time_sec is None:
            raise ValueError(f"Invalid time data for event at index {index}")

        description = self.get_param("EVENT", "DESCRIPTIONS", index=index, default="")

        return Event(
            trial=trial,
            context=context,
            label=label,
            time=timedelta(
                minutes=time_min, 
                seconds=time_sec
            ),
            description=description
        )
    
    def get_all_events(self, trial: Trial) -> list[Event]:
        """
        Extract all events from C3D file.
        
        Returns:
            List of Event instances
        """
        n_events = len(self.get_param("EVENT", "LABELS", default=[]))
        return [
            self.get_event(trial=trial, index=i)
            for i in range(n_events)
        ]

    def to_trial(self, 
                 name: str = '', 
                 timestamp: datetime | None = None,
                 capture_session: CaptureSession | None = None,
                 subjects: list[Subject] | None = None,
                 trial_id: int | None = None
                 ) -> Trial:
        """
        Convert the C3D data to a Trial instance with HDF5 storage.
        
        Args:
            name: Trial name
            timestamp: Trial timestamp
            capture_session: Associated capture session
            subjects: Associated subjects
            trial_id: Trial ID (required for HDF5 path generation)
        
        Returns:
            Trial instance with metadata and HDF5 path reference
        """
        if subjects is None:
            subjects = []
        
        # Extract metadata parameters
        parameters = {}
        # The PROCESSING group is not an official C3D parameter group, but Vicon uses it for subject parameters
        if "PROCESSING" in self.c3d.parameters:
            for key, value in self.c3d.parameters["PROCESSING"].items():
                arr = value.get("value", None)
                if arr is not None and len(arr) == 1:
                    parameters[key] = arr[0]
                else:
                    parameters[key] = arr
        
        # Extract marker metadata
        marker_labels = self.get_param("POINT", "LABELS", default=[])
        marker_rate = self.get_param("POINT", "RATE", default=0.0)
        marker_units = self.get_param("POINT", "UNITS", index=0, default="m")
        
        # Extract analog metadata
        analog_labels = self.get_param("ANALOG", "LABELS", default=[])
        analog_rate = self.get_param("ANALOG", "RATE", default=0.0)
        
        # Extract forceplate metadata
        forceplate_names = []
        forceplate_rate = analog_rate  # Force plates use analog rate
        if "platform" in self.c3d.data:
            forceplate_names = [f"ForcePlate_{i}" for i in range(len(self.c3d.data["platform"]))]
        
        # Get frame info
        first_frame = self.c3d.header["points"]["first_frame"]
        last_frame = self.c3d.header["points"]["last_frame"]
        n_frames = last_frame - first_frame + 1
        
        # Create Trial model with metadata
        trial = Trial(
            id=trial_id,
            name=name,
            timestamp=timestamp,
            capture_session=capture_session,
            subjects=subjects,
            parameters=parameters,
            marker_names=marker_labels,
            analog_names=analog_labels,
            forceplate_names=forceplate_names,
            marker_rate=marker_rate,
            analog_rate=analog_rate,
            forceplate_rate=forceplate_rate,
            n_frames=n_frames,
            first_frame=first_frame,
            last_frame=last_frame
        )
        
        # Extract events (stay in SQL - lightweight)
        trial.events = self.get_all_events(trial=trial)
        
        # Write time-series data to HDF5 if trial has an ID
        if trial_id is not None:
            self._write_to_hdf5(trial)
        
        return trial
    
    def _write_to_hdf5(self, trial: Trial) -> None:
        """
        Write time-series data from C3D to HDF5 file.
        
        Args:
            trial: Trial model with metadata
        """
        if trial.id is None:
            raise ValueError("Trial must have an ID before writing to HDF5")
        
        # Generate HDF5 path
        config = get_storage_config()
        hdf5_dir = Path(config.hdf5_base_dir) / f"trials_{trial.id // 1000:06d}"
        hdf5_dir.mkdir(parents=True, exist_ok=True)
        hdf5_path = hdf5_dir / f"trial_{trial.id:06d}.h5"
        trial.hdf5_path = str(hdf5_path)
        
        with HDF5TrialStorage(hdf5_path, trial_id=trial.id, mode='w') as storage:
            # Write markers (vectorized - no per-frame loops!)
            if "points" in self.c3d.data:
                marker_data = self.c3d.data["points"]  # Shape: (4, n_markers, n_frames)
                n_markers = marker_data.shape[1]
                n_frames = marker_data.shape[2]
                
                # Reshape to (n_frames, n_markers, 3) for xyz
                markers_xyz = np.transpose(marker_data[:3, :, :], (2, 1, 0))  # (n_frames, n_markers, 3)
                
                # Handle NaN values (convert to sentinel value for HDF5)
                markers_xyz = np.where(np.isnan(markers_xyz), -9999.0, markers_xyz)
                
                storage.write_markers(
                    data=markers_xyz,
                    marker_names=trial.marker_names,
                    rate=trial.marker_rate or 0.0,
                    units=self.get_param("POINT", "UNITS", index=0, default="m"),
                    first_frame=trial.first_frame
                )
            
            # Write analogs (vectorized)
            if "analogs" in self.c3d.data:
                analog_data = self.c3d.data["analogs"]  # Shape: (1, n_analogs, n_frames)
                # Reshape to (n_frames, n_analogs)
                analogs_values = analog_data[0, :, :].T  # (n_frames, n_analogs)
                
                # Handle NaN values
                analogs_values = np.where(np.isnan(analogs_values), 0.0, analogs_values)
                
                # Note: Scales and offsets are stored as metadata in Trial model
                # but not applied here - they can be applied at read time if needed
                
                storage.write_analogs(
                    data=analogs_values,
                    channel_names=trial.analog_names,
                    rate=trial.analog_rate or 0.0,
                    units="V",  # Base units before scaling
                    first_frame=trial.first_frame
                )
            
            # Write force plates (vectorized)
            if "platform" in self.c3d.data:
                for i, fp in enumerate(self.c3d.data["platform"]):
                    fp_name = trial.forceplate_names[i]
                    
                    # Extract force plate data
                    force = fp.get("force", np.zeros((3, 0)))  # Shape: (3, n_frames)
                    moment = fp.get("moment", np.zeros((3, force.shape[1])))
                    cop = fp.get("center_of_pressure", np.zeros((3, force.shape[1])))
                    
                    n_frames = force.shape[1]
                    
                    # Transpose to (n_frames, 3) format
                    forces = force.T  # (n_frames, 3)
                    moments = moment.T  # (n_frames, 3)
                    cop_data = cop.T  # (n_frames, 3)
                    
                    # Handle NaN values
                    forces = np.where(np.isnan(forces), 0.0, forces)
                    moments = np.where(np.isnan(moments), 0.0, moments)
                    cop_data = np.where(np.isnan(cop_data), 0.0, cop_data)
                    
                    # Get calibration data
                    cal_matrix = fp.get("cal_matrix", np.eye(6))
                    corners = fp.get("corners", np.zeros((4, 3)))
                    origin = fp.get("origin", np.zeros(3))
                    
                    storage.write_forceplate(
                        name=fp_name,
                        forces=forces,
                        moments=moments,
                        cop=cop_data,
                        rate=trial.forceplate_rate or 0.0,
                        cal_matrix=cal_matrix,
                        corners=corners,
                        origin=origin,
                        unit_force=fp.get("unit_force", "N"),
                        unit_moment=fp.get("unit_moment", "Nm"),
                        unit_position=fp.get("unit_position", "m")
                    )