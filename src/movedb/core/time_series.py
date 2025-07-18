"""Time series data structures for biomechanical trials."""

import warnings
from typing import Annotated

import ezc3d
import numpy as np
import pandera.polars as pa
import polars as pl
from pandera.typing.polars import DataFrame
from pydantic import AfterValidator, BaseModel, model_validator

from movedb.utils import get_c3d_param

# TODO: Consolidate data from Analogs and Points so that can share common functionality
class TimeSeriesGroup(BaseModel):
    first_frame: int
    last_frame: int
    rate: float

    @model_validator(mode="after")
    def validate_frames_and_rate(self):
        """
        Validate that first_frame is non-zero and less than last_frame and rate is positive.
        """
        assert self.first_frame >= 0, "first_frame must be non-negative"
        assert (
            self.first_frame < self.last_frame
        ), "first_frame must be less than last_frame"
        assert self.rate > 0, "rate must be positive"
        return self

    @property
    def total_frames(self):
        return self.last_frame - self.first_frame + 1

    def time_from_frame(self, frame: int) -> float:
        if frame < self.first_frame or frame > self.last_frame:
            raise ValueError("Frame out of bounds")
        return frame / self.rate

    @property
    def time(self) -> np.ndarray:
        """
        Return a time vector for the time series group.
        """
        if self.first_frame > 0:
            frame = self.first_frame - 1
        else:
            frame = 0
        return np.arange(frame, self.last_frame + 1) / self.rate


class MarkerSchema(pa.DataFrameModel):
    x: float = pa.Field(coerce=True, nullable=True)
    y: float = pa.Field(coerce=True, nullable=True)
    z: float = pa.Field(coerce=True, nullable=True)
    residual: float = pa.Field(coerce=True, nullable=True)
ValidMarkerData = Annotated[DataFrame[MarkerSchema], AfterValidator(MarkerSchema.validate)]


class MarkerTrajectory(BaseModel):
    """
    A marker trajectory represented as a Polars DataFrame with columns:
    x, y, z, residual, description
    """

    data: ValidMarkerData
    description: str = ""

    @classmethod
    def from_c3d(cls, c3d_object: ezc3d.c3d, index: int = 0) -> "MarkerTrajectory":
        """
        Create a MarkerTrajectory from a C3D object.
        """
        description = get_c3d_param(
            c3d_object,
            "POINT",
            "DESCRIPTIONS",
            index=index,
            default=cls.model_fields["description"].default,
        )
        return cls(
            data=DataFrame[MarkerSchema](
                {
                    "x": c3d_object.data["points"][0, index, :].tolist(),
                    "y": c3d_object.data["points"][1, index, :].tolist(),
                    "z": c3d_object.data["points"][2, index, :].tolist(),
                    "residual": c3d_object.data["meta_points"]["residuals"][
                        0, index, :
                    ].tolist(),
                }
            ),
            description=description,
        )

    @property
    def coords(self) -> np.ndarray:
        """Return coordinates as numpy array (n_frames, 3)"""
        return self.data.select(["x", "y", "z"]).to_numpy()

    @property
    def residual(self) -> np.ndarray:
        """Return residuals as numpy array (n_frames,)"""
        return self.data.select(["residual"]).to_numpy().flatten()

    def get_gaps(self, regions: list[tuple[int, int]] = []) -> list[tuple[int, int]]:
        """
        Find gaps in this marker trajectory.
        
        Args:
            regions: List of (start, end) tuples in relative frame indices (0-based)
        
        Returns:
            List of (start, end) tuples of gap ranges in relative frame indices
        """
        if not regions:
            regions = [(0, self.data.height - 1)]
        gaps = []
        for start, end in regions:
            # Ensure start and end are within bounds
            start = max(start, 0)
            end = min(end, self.data.height - 1)
            
            trimmed_data = self.data.slice(start, end - start + 1)
            if trimmed_data.height == 0:
                continue
            # Get indices of frames where data is missing
            missing_mask = (
                trimmed_data.select(pl.col("x").is_null() |
                                    pl.col("x").is_nan() | 
                                    pl.col("y").is_null() | 
                                    pl.col("y").is_nan() | 
                                    pl.col("z").is_null() | 
                                    pl.col("z").is_nan())
            ).to_numpy().flatten()
            if not np.any(missing_mask):
                continue
            # Convert mask to frame ranges using diff to find transitions
            # Add padding to handle edge cases
            padded_mask = np.concatenate(([False], missing_mask, [False]))
            # Find transitions: False->True (gap starts) and True->False (gap ends)
            diff = np.diff(padded_mask.astype(int))
            gap_starts = np.where(diff == 1)[0]  # Transitions from 0 to 1
            gap_ends = np.where(diff == -1)[0] - 1  # Transitions from 1 to 0, adjust by -1
            
            # Convert to relative frame indices (adjusted for the start offset)
            for gap_start, gap_end in zip(gap_starts, gap_ends):
                gaps.append((gap_start + start, gap_end + start))
        return gaps

    def find_full_frames(self, regions: list[tuple[int, int]] = []) -> list[int]:
        """
        Find all frames where this marker has complete data (no NaN/null values).
        
        Args:
            regions: List of (start, end) tuples in relative frame indices (0-based)
        
        Returns:
            List of relative frame indices where marker has complete data
        """
        if not regions:
            regions = [(0, self.data.height - 1)]
        
        full_frames = []
        for start, end in regions:
            # Ensure start and end are within bounds
            start = max(start, 0)
            end = min(end, self.data.height - 1)
            
            # Get the region data
            region_data = self.data.slice(start, end - start + 1)
            
            # Create mask for complete data (not null and not NaN)
            complete_mask = (
                region_data.select(
                    ~(pl.col("x").is_null() | pl.col("x").is_nan() |
                      pl.col("y").is_null() | pl.col("y").is_nan() |
                      pl.col("z").is_null() | pl.col("z").is_nan())
                )
            ).to_numpy().flatten()
            
            # Get indices where data is complete
            complete_indices = np.where(complete_mask)[0]
            
            # Convert to absolute relative indices (adjust for start offset)
            full_frames.extend(complete_indices + start)
        
        return sorted(full_frames)

    def __len__(self) -> int:
        return len(self.data)


class Points(TimeSeriesGroup):
    units: str = "m"
    trajectories: dict[str, MarkerTrajectory]

    @classmethod
    def from_c3d(cls, c3d_object: ezc3d.c3d) -> "Points":
        if not "POINT" in c3d_object.parameters:
            raise ValueError("C3D object does not contain POINT parameters.")
        if not "points" in c3d_object.data:
            raise ValueError("C3D object does not contain point data.")
        header_first_frame = c3d_object.header["points"]["first_frame"]
        header_last_frame = c3d_object.header["points"]["last_frame"]
        header_rate = c3d_object.header["points"]["frame_rate"]

        camera_rate = get_c3d_param(
            c3d_object, "TRIAL", "CAMERA_RATE", default=header_rate
        )
        point_rate = get_c3d_param(c3d_object, "POINT", "RATE", default=camera_rate)
        if camera_rate != header_rate:
            warnings.warn(
                f"Camera rate {camera_rate} does not match header rate {header_rate}. Defaulting to camera rate."
            )
        if point_rate != camera_rate:
            warnings.warn(
                f"Point rate {point_rate} does not match camera rate {camera_rate}. Defaulting to point rate."
            )

        labels = get_c3d_param(c3d_object, "POINT", "LABELS", default=[])
        units = get_c3d_param(
            c3d_object, "POINT", "UNITS", default=[cls.model_fields["units"].default]
        )[0]

        return cls(
            first_frame=header_first_frame,
            last_frame=header_last_frame,
            rate=point_rate,
            units=units,
            trajectories={
                label: MarkerTrajectory.from_c3d(c3d_object, index=i)
                for i, label in enumerate(labels)
            },
        )

    @model_validator(mode="after")
    def validate_trajectory_lengths(self) -> "Points":
        """Ensure all trajectories have the same length matching total_frames"""
        expected_length = self.total_frames

        for marker_name, trajectory in self.trajectories.items():
            if len(trajectory) != expected_length:
                raise ValueError(
                    f"Marker '{marker_name}' has {len(trajectory)} frames, "
                    f"expected {expected_length} frames"
                )
        return self

    def to_df(self, include_residual: bool = False) -> pl.DataFrame:
        """
        Convert the Points object to a Polars DataFrame.
        Each marker's coordinates will be separate columns (marker_x, marker_y, marker_z,
        marker_residual if include_residual is True).
        """
        if not self.trajectories:
            return pl.DataFrame()

        dfs = []
        for name, trajectory in self.trajectories.items():
            traj_df = trajectory.data.rename(
                {
                    "x": f"{name}_x",
                    "y": f"{name}_y",
                    "z": f"{name}_z",
                    "residual": f"{name}_residual",
                }
            )
            if not include_residual:
                traj_df = traj_df.drop(f"{name}_residual")
            dfs.append(traj_df)
        # Concatenate horizontally
        return pl.concat(dfs, how="horizontal")

    def to_dict(self, include_residual: bool = False) -> dict[str, np.ndarray]:
        """
        Convert the Points object to a dictionary of marker names to numpy arrays.
        Each array will have shape (n_frames, 3) or (n_frames, 4) if include_residual is True.
        """
        result = {}
        for name, trajectory in self.trajectories.items():
            coords = trajectory.coords
            if include_residual:
                residual = trajectory.residual.reshape(-1, 1)
                coords = np.hstack((coords, residual))
            result[name] = coords
        return result

    def get_marker_coords(
        self, marker_name: str, frame: int | None = None
    ) -> np.ndarray:
        """Get marker coordinates, optionally at a specific frame"""
        if marker_name not in self.trajectories:
            raise ValueError(f"Marker '{marker_name}' not found in trajectories")
        marker = self.trajectories[marker_name]

        if frame is None:
            return marker.coords

        if frame < self.first_frame or frame > self.last_frame:
            raise IndexError(f"Frame {frame} out of bounds")

        # Convert absolute frame to relative index
        frame_idx = frame - self.first_frame
        return marker.coords[frame_idx]

    def get_gaps(
        self,
        marker_names: list[str] | None = None,
        regions: list[tuple[int, int] | tuple[float, float]] | None = None,
    ) -> dict[str, list[tuple[int, int]]]:
        """
        Check for gaps in point data for specified markers and regions.
        A gap is defined as any frame in the region where the marker data is missing (NaN).
        Returns a dictionary with marker names as keys and lists of (start, end) tuples indicating integer frame gaps.

        If no markers or regions are specified, checks all markers and the entire trial duration.
        """
        gaps = {}
        if marker_names is None:
            marker_names = list(self.trajectories.keys())
        
        # Convert regions to relative frame indices
        if regions is None:
            relative_regions = [(0, self.total_frames - 1)]
        else:
            relative_regions = []
            for start, end in regions:
                # Convert time to frames if needed
                start = int(start * self.rate) if isinstance(start, float) else start
                end = int(end * self.rate) if isinstance(end, float) else end
                # Convert absolute frames to relative indices
                rel_start = max(start - self.first_frame, 0)
                rel_end = min(end - self.first_frame, self.total_frames - 1)
                relative_regions.append((rel_start, rel_end))
        
        # Get gaps for each marker
        for marker in marker_names:
            if marker not in self.trajectories:
                gaps[marker] = []
                continue
            
            marker_gaps = self.trajectories[marker].get_gaps(relative_regions)
            # Convert relative gaps back to absolute frame numbers
            absolute_gaps = [
                (gap_start + self.first_frame, gap_end + self.first_frame)
                for gap_start, gap_end in marker_gaps
            ]
            gaps[marker] = absolute_gaps
        
        return gaps
    
    def find_full_frames(self, marker_names: list[str] | None = None) -> list[int]:
        """
        Find all frames where all specified markers have data.
        If no markers are specified, checks all markers.
        Returns a list of frame indices (absolute frame numbers).
        """
        if marker_names is None:
            marker_names = list(self.trajectories.keys())
        
        # If no markers specified or no trajectories, return empty list
        if not marker_names or not self.trajectories:
            return []
        
        # Check if all specified markers exist
        missing_markers = [m for m in marker_names if m not in self.trajectories]
        if missing_markers:
            return []  # If any marker is missing, no frames can be full
        
        # Start with all possible frames
        full_frames = set(range(self.first_frame, self.last_frame + 1))
        
        # Get gaps for all specified markers
        gaps = self.get_gaps(marker_names)
        
        # Remove all frames that have gaps in any marker
        for marker in marker_names:
            marker_gaps = gaps.get(marker, [])
            for gap_start, gap_end in marker_gaps:
                # Remove all frames in this gap
                gap_frames = set(range(gap_start, gap_end + 1))
                full_frames -= gap_frames
        
        return sorted(full_frames)

    def add_marker(
        self,
        name: str,
        x: list,
        y: list,
        z: list,
        residual: list | None = None,
        description: str = "",
    ):
        """Add a new marker trajectory"""
        n_frames = self.total_frames

        # Validate lengths
        if len(x) != n_frames or len(y) != n_frames or len(z) != n_frames:
            raise ValueError(f"Coordinate arrays must have length {n_frames}")

        if residual is None:
            residual = [0.0] * n_frames

        trajectory = MarkerTrajectory(
            data=DataFrame[MarkerSchema](
                {"x": x, "y": y, "z": z, "residual": residual}
            ),
            description=description,
        )
        self.trajectories[name] = trajectory


class AnalogChannel(BaseModel):
    """Each analog channel can have different units"""

    data: list[float]  # TODO: Should this be a sequence type like np.ndarray?
    units: str = "V"
    scale: float = 1.0
    offset: float = 0.0
    description: str = ""

    @classmethod
    def from_c3d(cls, c3d_obj: ezc3d.c3d, index: int = 0) -> "AnalogChannel":
        analog_data = c3d_obj.data["analogs"][0, index, :].tolist()
        units = get_c3d_param(
            c3d_obj,
            "ANALOG",
            "UNITS",
            index=index,
            default=cls.model_fields["units"].default,
        )
        scale = get_c3d_param(
            c3d_obj,
            "ANALOG",
            "SCALE",
            index=index,
            default=cls.model_fields["scale"].default,
        )
        offset = get_c3d_param(
            c3d_obj,
            "ANALOG",
            "OFFSET",
            index=index,
            default=cls.model_fields["offset"].default,
        )
        description = get_c3d_param(
            c3d_obj,
            "ANALOG",
            "DESCRIPTIONS",
            index=index,
            default=cls.model_fields["description"].default,
        )

        return cls(
            data=analog_data,
            units=units,
            scale=scale,
            offset=offset,
            description=description,
        )

    def __len__(self) -> int:
        return len(self.data)


class Analogs(TimeSeriesGroup):
    # Analogs store different channels each of which could have different units
    channels: dict[str, AnalogChannel]
    gen_scale: float = 1.0  # General scale factor for all channels

    @classmethod
    def from_c3d(cls, c3d_object: ezc3d.c3d) -> "Analogs":
        if not "ANALOG" in c3d_object.parameters:
            raise ValueError("C3D object does not contain ANALOG parameters.")
        if not "analogs" in c3d_object.data:
            raise ValueError("C3D object does not contain analog data.")

        header_first_frame = c3d_object.header["analogs"]["first_frame"]
        header_last_frame = c3d_object.header["analogs"]["last_frame"]
        header_rate = c3d_object.header["analogs"]["frame_rate"]

        analog_rate = get_c3d_param(c3d_object, "ANALOG", "RATE", default=header_rate)
        if analog_rate != header_rate:
            warnings.warn(
                f"Analog rate {analog_rate} does not match header rate {header_rate}. Defaulting to analog rate."
            )

        labels = get_c3d_param(c3d_object, "ANALOG", "LABELS", default=[])

        gen_scale = get_c3d_param(c3d_object, "ANALOG", "GEN_SCALE", default=[1.0])[0]

        return cls(
            first_frame=header_first_frame,  # TODO: Maybe ignore header and set this based on data?
            last_frame=header_last_frame,
            rate=analog_rate,
            gen_scale=gen_scale,
            channels={
                label: AnalogChannel.from_c3d(c3d_object, index=i)
                for i, label in enumerate(labels)
            },
        )

    @model_validator(mode="after")
    def validate_channel_lengths(self) -> "Analogs":
        """Ensure all channels have the same length matching total_frames"""
        expected_length = self.total_frames

        for channel_name, channel in self.channels.items():
            if len(channel) != expected_length:
                raise ValueError(
                    f"Channel '{channel_name}' has {len(channel)} frames, "
                    f"expected {expected_length} frames"
                )
        return self

    def to_df(self) -> pl.DataFrame:
        """
        Convert the Analogs object to a Polars DataFrame.
        Each channel will be a column in the DataFrame.
        WARNING: This decouples the channels from their original units.
        """
        if not self.channels:
            return pl.DataFrame()
        dfs = []
        for name, channel in self.channels.items():
            channel_df = pl.DataFrame({name: channel.data})
            dfs.append(channel_df)

        # Concatenate horizontally
        return pl.concat(dfs, how="horizontal")
