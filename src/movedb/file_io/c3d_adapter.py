from typing import Any
import ezc3d
import numpy as np
import polars as pl
from ..models import (
    Event, 
    Analog,
    Marker,
    ForcePlate,
    Trial
)
from pydantic import BaseModel

class C3DAdapter(BaseModel):
    """
    Adapter class for converting C3D file data to MoveDB models.
    Handles parameter access, error handling, and data conversion.
    """
    c3d: ezc3d.c3d
    
    @classmethod
    def from_file(cls, file_path: str, extract_forceplat_data: bool = True) -> "C3DAdapter":
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
        value = param.get("value", {})
        
        if index is not None and (isinstance(value, list) or isinstance(value, np.ndarray)):
            if index < 0 or index >= len(value):
                raise IndexError(f"Index {index} out of range for parameter '{keys}'")
            return value[index]
        return value if value is not None else default

    def get_event(self, index: int = 0) -> Event:
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
        if times.shape[1] <= index:
            raise ValueError(f"No time data for event at index {index}")
            
        time_min, time_sec = times[:, index]
        if time_min is None or time_sec is None:
            raise ValueError(f"Invalid time data for event at index {index}")
            
        description = self.get_param("EVENT", "DESCRIPTIONS", index=index, default="")
        
        return Event(
            context=context,
            label=label,
            time=time_min * 60 + time_sec,  # Convert from (min, sec) to sec
            description=description
        )

    def get_force_plate(self, index: int = 0) -> ForcePlate:
        """
        Extract force plate data from C3D file.
        
        Args:
            index: Index of the force plate to extract
            
        Returns:
            ForcePlate model instance
            
        Raises:
            ValueError: If force plate data is missing
            IndexError: If force plate index is out of range
        """
        if "platform" not in self.c3d.data:
            raise ValueError(
                "C3D object does not contain force plate data. "
                "Make sure to set extract_forceplat_data=True in ezc3d.c3d constructor."
            )
            
        c3d_fp = self.c3d.data["platform"]
        if index >= len(c3d_fp):
            raise IndexError(
                f"Index {index} out of range for force platforms. Available: {len(c3d_fp)}"
            )
            
        fp: dict = c3d_fp[index]
        force = fp.get("force", np.zeros((3, 0)))
        n_frames = force.shape[1]
        
        moment = fp.get("moment", np.zeros((3, n_frames)))
        position = fp.get("center_of_pressure", np.zeros((3, n_frames)))
        free_moment = fp.get("Tz", np.zeros((3, n_frames)))

        # Create timestamps based on the point frame rate
        rate = self.get_param("POINT", "RATE", default=0.0)
        timestamps = np.arange(n_frames) / rate
        
        data_dict = {
            "timestamp": timestamps,
            "force_x": force[0, :],
            "force_y": force[1, :],
            "force_z": force[2, :],
            "moment_x": moment[0, :],
            "moment_y": moment[1, :],
            "moment_z": moment[2, :],
            "cop_x": position[0, :],
            "cop_y": position[1, :],
            "cop_z": position[2, :],
            "freemoment_x": free_moment[0, :],
            "freemoment_y": free_moment[1, :],
            "freemoment_z": free_moment[2, :]
        }
        
        fp_model = ForcePlate(
            unit_force=fp.get("unit_force", "N"),
            unit_moment=fp.get("unit_moment", "Nm"),
            unit_position=fp.get("unit_position", "m"),
            rate=rate,
            cal_matrix = fp.get("cal_matrix", np.eye(6)),
            corners = fp.get("corners", np.zeros((4, 3))),
            origin = fp.get("origin", np.zeros(3)),
            first_frame=self.c3d.header["points"]["first_frame"]
        )
        fp_model.set_data(pl.DataFrame(data_dict))
        
        return fp_model

    def get_marker(self, index: int = 0) -> Marker:
        """
        Extract marker data from C3D file.
        
        Args:
            index: Index of the marker to extract
            
        Returns:
            Marker model instance
            
        Raises:
            ValueError: If marker data is missing
        """
        if "points" not in self.c3d.data:
            raise ValueError("C3D object does not contain point data")
            
        # Get timestamps based on the point frame rate
        n_frames = self.c3d.data["points"].shape[2]
        rate = self.get_param("POINT", "RATE", default=0.0)
        timestamps = np.arange(n_frames) / rate
        
        data_dict = {
            "timestamp": timestamps,
            "x": self.c3d.data["points"][0, index, :],
            "y": self.c3d.data["points"][1, index, :],
            "z": self.c3d.data["points"][2, index, :],
            "residual": self.c3d.data["meta_points"]["residuals"][0, index, :]
        }
        
        marker = Marker(
            description=self.get_param("POINT", "DESCRIPTIONS", index=index, default=""),
            units=self.get_param("POINT", "UNITS", index=0, default="m"),
            rate=rate,
            first_frame=self.c3d.header["points"]["first_frame"]
        )
        marker.set_data(pl.DataFrame(data_dict))
        
        return marker

    def get_analog(self, index: int = 0) -> Analog:
        """
        Extract analog channel data from C3D file.
        
        Args:
            index: Index of the analog channel to extract
            
        Returns:
            Analog model instance
            
        Raises:
            ValueError: If analog data is missing
        """
        if "analogs" not in self.c3d.data:
            raise ValueError("C3D object does not contain analog data")
            
        # Get timestamps based on the analog frame rate
        n_frames = self.c3d.data["analogs"].shape[2]
        rate = self.get_param("ANALOG", "RATE", default=0.0)
        timestamps = np.arange(n_frames) / rate
        
        data_dict = {
            "timestamp": timestamps,
            "value": self.c3d.data["analogs"][0, index, :]
        }
        
        analog = Analog(
            units=self.get_param("ANALOG", "UNITS", index=index, default="V"),
            scale=self.get_param("ANALOG", "SCALE", index=index, default=1.0),
            offset=self.get_param("ANALOG", "OFFSET", index=index, default=0.0),
            description=self.get_param("ANALOG", "DESCRIPTIONS", index=index, default=""),
            rate=rate,
            first_frame=self.c3d.header["analogs"]["first_frame"]
        )
        analog.set_data(pl.DataFrame(data_dict))
        
        return analog

    def get_all_markers(self) -> dict[str, Marker]:
        """
        Extract all markers from C3D file.
        
        Returns:
            Dictionary mapping marker labels to Marker instances
        """
        labels = self.get_param("POINT", "LABELS", default=[])
        return {
            label: self.get_marker(index=i)
            for i, label in enumerate(labels)
        }

    def get_all_analogs(self) -> dict[str, Analog]:
        """
        Extract all analog channels from C3D file.
        
        Returns:
            Dictionary mapping channel labels to Analog instances
        """
        labels = self.get_param("ANALOG", "LABELS", default=[])
        return {
            label: self.get_analog(index=i)
            for i, label in enumerate(labels)
        }

    def get_all_force_plates(self) -> list[ForcePlate]:
        """
        Extract all force plates from C3D file.
        
        Returns:
            List of ForcePlate instances
        """
        if "platform" not in self.c3d.data:
            return []
            
        return [
            self.get_force_plate(index=i)
            for i in range(len(self.c3d.data["platform"]))
        ]

    def get_all_events(self) -> list[Event]:
        """
        Extract all events from C3D file.
        
        Returns:
            List of Event instances
        """
        if "EVENT" not in self.c3d.parameters:
            return []
            
        n_events = len(self.get_param("EVENT", "LABELS", default=[]))
        return [
            self.get_event(index=i)
            for i in range(n_events)
        ]

    def to_trial(self) -> Trial:
        """
        Convert the C3D data to a Trial instance.
        
        Returns:
            Trial instance populated with data from the C3D file
        """
        return Trial(
            markers=self.get_all_markers(),
            analogs=self.get_all_analogs(),
            forceplates=self.get_all_force_plates(),
            events=self.get_all_events()
        )