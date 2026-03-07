"""Converters between core models, Polars DataFrames, and Parquet files."""

import json
import numpy as np
import polars as pl
from typing import Any, Literal, Annotated, Union
from pathlib import Path
from pydantic import Discriminator
from ..core import (
    AnalogData,
    Event,
    ForceplateData,
    MarkerData,
    AnalogMeta,
    ForceplateMeta,
    MarkerMeta,
)

# Discriminated union of all signal metadata types.
# Used as Parquet file-level metadata: the ``type`` field determines
# which concrete metadata model to instantiate on read.
#
# Usage:
#   from pydantic import TypeAdapter
#   ta = TypeAdapter(SignalMeta)
#   meta = ta.validate_python(raw_dict)   # -> MarkerMeta | AnalogMeta | ForceplateMeta
SignalMeta = Annotated[
    Union[MarkerMeta, AnalogMeta, ForceplateMeta],
    Discriminator("type"),
]


def write_parquet(
    df: pl.DataFrame,
    path: Path | str,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """
    Write a Polars DataFrame to a Parquet file with optional movedb metadata.

    Metadata is stored as a JSON string under the ``movedb`` key in the
    Parquet file's key-value metadata, making the files self-describing.

    Args:
        df: Polars DataFrame to write.
        path: Output file path.
        metadata: Optional dict of movedb metadata (rate, units, names, etc.).

    Returns:
        The resolved Path that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    parquet_meta = {"movedb": json.dumps(metadata)} if metadata is not None else None
    df.write_parquet(path, metadata=parquet_meta)
    return path


def read_parquet(path: Path | str) -> tuple[pl.DataFrame, dict[str, Any] | None]:
    """
    Read a Parquet file and extract any embedded movedb metadata.

    Args:
        path: Path to the Parquet file.

    Returns:
        Tuple of (DataFrame, metadata dict or None).
    """
    path = Path(path)
    df = pl.read_parquet(path)
    file_meta = pl.read_parquet_metadata(path)
    movedb_meta = json.loads(file_meta["movedb"]) if "movedb" in file_meta else None
    return df, movedb_meta


# ---------------------------------------------------------------------------
# Core model -> Polars DataFrame
# ---------------------------------------------------------------------------


def markers_to_polars(
    marker_data: MarkerData,
    format: Literal["long", "wide"] = "wide",
    trial_name: str | None = None,
) -> pl.DataFrame:
    """
    Convert marker data to a Polars DataFrame.

    Args:
        marker_data: MarkerData instance with trajectory arrays.
        format: Output format
            - 'wide': One row per frame. Each marker is a Struct({x, y, z})
              column (with an optional ``residual`` field).
            - 'long': One row per (frame, marker) with flat columns
              [time, frame, marker_name, x, y, z].
        trial_name: If provided, a 'trial_name' column is added.

    Returns:
        Polars DataFrame in specified format.
    """
    data = np.asarray(marker_data.data)  # (n_frames, n_markers, 3)
    marker_names = marker_data.names
    rate = marker_data.rate
    first_frame = marker_data.first_frame
    has_residuals = marker_data.residuals is not None

    n_frames = data.shape[0]
    n_markers = data.shape[1]

    time = np.arange(n_frames) / rate
    frames = np.arange(first_frame, first_frame + n_frames)

    if format == "wide":
        # Build base DataFrame with time and frame
        base_dict: dict[str, Any] = {"time": time, "frame": frames}
        if trial_name is not None:
            base_dict["trial_name"] = [trial_name] * n_frames
        df = pl.DataFrame(base_dict)

        # Add each marker as a Struct({x, y, z}) column
        residuals = np.asarray(marker_data.residuals) if has_residuals else None
        struct_cols = []
        for i, name in enumerate(marker_names):
            fields = [
                pl.Series("x", data[:, i, 0]),
                pl.Series("y", data[:, i, 1]),
                pl.Series("z", data[:, i, 2]),
            ]
            if residuals is not None:
                fields.append(pl.Series("residual", residuals[:, i]))
            struct_cols.append(pl.struct(fields).alias(name))

        return df.with_columns(struct_cols)

    elif format == "long":
        time_repeated = np.repeat(time, n_markers)
        frame_repeated = np.repeat(frames, n_markers)
        marker_names_repeated = np.tile(marker_names, n_frames)
        xyz_data = data.reshape(-1, 3)

        df_dict: dict[str, Any] = {
            "time": time_repeated,
            "frame": frame_repeated,
            "marker_name": marker_names_repeated,
            "x": xyz_data[:, 0],
            "y": xyz_data[:, 1],
            "z": xyz_data[:, 2],
        }

        if trial_name is not None:
            df_dict["trial_name"] = [trial_name] * len(time_repeated)

        if has_residuals:
            residuals = np.asarray(marker_data.residuals)
            df_dict["residual"] = residuals.flatten()

        return pl.DataFrame(df_dict)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def analogs_to_polars(
    analog_data: AnalogData,
    format: Literal["long", "wide"] = "wide",
    trial_name: str | None = None,
) -> pl.DataFrame:
    """
    Convert analog data to a Polars DataFrame.

    Args:
        analog_data: AnalogData instance with channel arrays.
        format: Output format
            - 'wide': One row per frame with a scalar column per channel.
            - 'long': One row per (frame, channel) with columns
              [time, frame, channel_name, value].
        trial_name: If provided, a 'trial_name' column is added.

    Returns:
        Polars DataFrame in specified format.
    """
    data = np.asarray(analog_data.data)  # (n_frames, n_channels)
    channel_names = analog_data.names
    rate = analog_data.rate
    first_frame = analog_data.first_frame

    n_frames = data.shape[0]
    n_channels = data.shape[1]

    time = np.arange(n_frames) / rate
    frames = np.arange(first_frame, first_frame + n_frames)

    if format == "wide":
        df_dict: dict[str, Any] = {"time": time, "frame": frames}
        if trial_name is not None:
            df_dict["trial_name"] = [trial_name] * n_frames
        for i, channel_name in enumerate(channel_names):
            df_dict[channel_name] = data[:, i]
        return pl.DataFrame(df_dict)

    elif format == "long":
        time_repeated = np.repeat(time, n_channels)
        frame_repeated = np.repeat(frames, n_channels)
        channel_names_repeated = np.tile(channel_names, n_frames)
        values = data.flatten()

        df_dict = {
            "time": time_repeated,
            "frame": frame_repeated,
            "channel_name": channel_names_repeated,
            "value": values,
        }
        if trial_name is not None:
            df_dict["trial_name"] = [trial_name] * len(time_repeated)
        return pl.DataFrame(df_dict)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def forceplates_to_polars(
    forceplate_data: ForceplateData,
    format: Literal["long", "wide"] = "wide",
    trial_name: str | None = None,
) -> pl.DataFrame:
    """
    Convert force plate data to a Polars DataFrame.

    Args:
        forceplate_data: ForceplateData instance (multi-plate container).
            Arrays are shaped ``(n_frames, n_plates, 3)``.
        format: Output format
            - 'wide': One row per frame. Each plate is a nested
              ``Struct({force: Struct({x,y,z}), moment: …, cop: …})`` column.
            - 'long': One row per (frame, plate, variable, axis) with flat
              columns [time, frame, fp_name, variable, axis, value].
        trial_name: If provided, a 'trial_name' column is added.

    Returns:
        Polars DataFrame in specified format.
    """
    forces = np.asarray(forceplate_data.forces)  # (n_frames, n_plates, 3)
    moments = np.asarray(forceplate_data.moments)  # (n_frames, n_plates, 3)
    cop = np.asarray(forceplate_data.cop)  # (n_frames, n_plates, 3)
    names = forceplate_data.names
    time = np.asarray(forceplate_data.time_vector)
    frames = np.asarray(forceplate_data.frame_vector)
    n_frames = forceplate_data.num_frames

    if format == "wide":
        base_dict: dict[str, Any] = {"time": time, "frame": frames}
        if trial_name is not None:
            base_dict["trial_name"] = [trial_name] * n_frames
        df = pl.DataFrame(base_dict)

        # Build a nested struct column per plate:
        # FP_name -> Struct({force: Struct({x,y,z}), moment: ..., cop: ...})
        plate_cols = []
        for i, fp_name in enumerate(names):
            force_struct = pl.struct(
                pl.Series("x", forces[:, i, 0]),
                pl.Series("y", forces[:, i, 1]),
                pl.Series("z", forces[:, i, 2]),
            ).alias("force")

            moment_struct = pl.struct(
                pl.Series("x", moments[:, i, 0]),
                pl.Series("y", moments[:, i, 1]),
                pl.Series("z", moments[:, i, 2]),
            ).alias("moment")

            cop_struct = pl.struct(
                pl.Series("x", cop[:, i, 0]),
                pl.Series("y", cop[:, i, 1]),
                pl.Series("z", cop[:, i, 2]),
            ).alias("cop")

            plate_cols.append(
                pl.struct(force_struct, moment_struct, cop_struct).alias(fp_name)
            )

        return df.with_columns(plate_cols)

    elif format == "long":
        variables = [
            "force",
            "force",
            "force",
            "moment",
            "moment",
            "moment",
            "cop",
            "cop",
            "cop",
        ]
        axes = ["x", "y", "z", "x", "y", "z", "x", "y", "z"]

        plate_dfs: list[pl.DataFrame] = []
        for i, fp_name in enumerate(names):
            all_values = np.column_stack(
                [
                    forces[:, i, :],
                    moments[:, i, :],
                    cop[:, i, :],
                ]
            )  # (n_frames, 9)

            time_repeated = np.repeat(time, 9)
            frame_repeated = np.repeat(frames, 9)

            df_dict: dict[str, Any] = {
                "time": time_repeated,
                "frame": frame_repeated,
                "fp_name": [fp_name] * (n_frames * 9),
                "variable": np.tile(variables, n_frames),
                "axis": np.tile(axes, n_frames),
                "value": all_values.flatten(),
            }
            if trial_name is not None:
                df_dict["trial_name"] = [trial_name] * (n_frames * 9)
            plate_dfs.append(pl.DataFrame(df_dict))

        return pl.concat(plate_dfs)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def events_to_polars(
    events: list[Event],
    trial_name: str | None = None,
) -> pl.DataFrame:
    """
    Convert a list of Event models to a Polars DataFrame.

    Args:
        events: List of Event instances.
        trial_name: If provided, a 'trial_name' column is added.

    Returns:
        Polars DataFrame with columns [context, label, time, frame, description]
        (and trial_name if provided).
    """
    if not events:
        schema: dict[str, type[pl.DataType]] = {
            "context": pl.Utf8,
            "label": pl.Utf8,
            "time": pl.Float64,
            "frame": pl.Int64,
            "description": pl.Utf8,
        }
        if trial_name is not None:
            schema["trial_name"] = pl.Utf8
        return pl.DataFrame(schema=schema)

    rows: list[dict[str, Any]] = []
    for event in events:
        row: dict[str, Any] = {
            "context": event.context,
            "label": event.label,
            "time": event.time,
            "frame": event.frame,
            "description": event.description,
        }
        if trial_name is not None:
            row["trial_name"] = trial_name
        rows.append(row)

    return pl.DataFrame(rows)
