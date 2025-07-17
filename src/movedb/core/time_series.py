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
            prefix = name
            traj_df = trajectory.data.rename(
                {
                    "x": f"{prefix}_x",
                    "y": f"{prefix}_y",
                    "z": f"{prefix}_z",
                    "residual": f"{prefix}_residual",
                }
            )
            if not include_residual:
                traj_df = traj_df.drop(f"{prefix}_residual")
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
