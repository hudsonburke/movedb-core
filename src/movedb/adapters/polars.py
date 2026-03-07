"""Converters between core models, Polars DataFrames, and Parquet files."""

import numpy as np
import polars as pl
from typing import Any, Literal

from ..core import AnalogData, Event, ForceplateData, MarkerData


def markers_to_polars(
    marker_data: MarkerData,
    format: Literal["long", "wide"] = "long",
    trial_name: str | None = None,
) -> pl.DataFrame:
    """
    Convert marker data to Polars DataFrame.

    Args:
        marker_data: MarkerData instance with trajectory arrays.
        format: Output format
            - 'long': One row per (frame, marker) with columns [time, frame, marker_name, x, y, z]
            - 'wide': One row per frame with columns [time, frame, marker1_x, marker1_y, marker1_z, ...]
        trial_name: If provided, a 'trial_name' column is added (used for session-level files).

    Returns:
        Polars DataFrame in specified format.
    """
    data = np.asarray(marker_data.data)  # (n_frames, n_markers, 3)
    marker_names = marker_data.names
    rate = marker_data.rate
    first_frame = marker_data.first_frame

    n_frames = data.shape[0]
    n_markers = data.shape[1]

    # Create time and frame arrays
    time = np.arange(n_frames) / rate
    frames = np.arange(first_frame, first_frame + n_frames)

    if format == "long":
        # Long format: repeat time/frame for each marker
        time_repeated = np.repeat(time, n_markers)
        frame_repeated = np.repeat(frames, n_markers)
        marker_names_repeated = np.tile(marker_names, n_frames)

        # Reshape data: (n_frames, n_markers, 3) -> (n_frames * n_markers, 3)
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

        # Add residuals if present
        residuals = np.asarray(marker_data.residuals)
        if residuals is not None:
            df_dict["residual"] = residuals.flatten()

        return pl.DataFrame(df_dict)

    elif format == "wide":
        # Wide format: one column per marker coordinate
        df_dict = {
            "time": time,
            "frame": frames,
        }

        if trial_name is not None:
            df_dict["trial_name"] = [trial_name] * n_frames

        # Add columns for each marker's x, y, z
        for i, marker_name in enumerate(marker_names):
            df_dict[f"{marker_name}_x"] = data[:, i, 0]
            df_dict[f"{marker_name}_y"] = data[:, i, 1]
            df_dict[f"{marker_name}_z"] = data[:, i, 2]

        # Add residuals if present
        residuals = np.asarray(marker_data.residuals)
        if residuals is not None:
            for i, marker_name in enumerate(marker_names):
                df_dict[f"{marker_name}_residual"] = residuals[:, i]

        return pl.DataFrame(df_dict)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def analogs_to_polars(
    analog_data: AnalogData,
    format: Literal["long", "wide"] = "long",
    trial_name: str | None = None,
) -> pl.DataFrame:
    """
    Convert analog data to Polars DataFrame.

    Args:
        analog_data: AnalogData instance with channel arrays.
        format: Output format
            - 'long': One row per (frame, channel) with columns [time, frame, channel_name, value]
            - 'wide': One row per frame with columns [time, frame, channel1, channel2, ...]
        trial_name: If provided, a 'trial_name' column is added (used for session-level files).

    Returns:
        Polars DataFrame in specified format.
    """
    data = np.asarray(analog_data.data)  # (n_frames, n_channels)
    channel_names = analog_data.names
    rate = analog_data.rate
    first_frame = analog_data.first_frame

    n_frames = data.shape[0]
    n_channels = data.shape[1]

    # Create time and frame arrays
    time = np.arange(n_frames) / rate
    frames = np.arange(first_frame, first_frame + n_frames)

    if format == "long":
        # Long format: repeat time/frame for each channel
        time_repeated = np.repeat(time, n_channels)
        frame_repeated = np.repeat(frames, n_channels)
        channel_names_repeated = np.tile(channel_names, n_frames)

        # Reshape data: (n_frames, n_channels) -> (n_frames * n_channels,)
        values = data.flatten()

        df_dict: dict[str, Any] = {
            "time": time_repeated,
            "frame": frame_repeated,
            "channel_name": channel_names_repeated,
            "value": values,
        }

        if trial_name is not None:
            df_dict["trial_name"] = [trial_name] * len(time_repeated)

        return pl.DataFrame(df_dict)

    elif format == "wide":
        # Wide format: one column per channel
        df_dict = {
            "time": time,
            "frame": frames,
        }

        if trial_name is not None:
            df_dict["trial_name"] = [trial_name] * n_frames

        # Add columns for each channel
        for i, channel_name in enumerate(channel_names):
            df_dict[channel_name] = data[:, i]

        return pl.DataFrame(df_dict)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def forceplates_to_polars(
    forceplate_data: ForceplateData,
    format: Literal["long", "wide"] = "wide",
    trial_name: str | None = None,
) -> pl.DataFrame:
    """
    Convert force plate data to Polars DataFrame.

    The ForceplateData model stores stacked arrays with shape (n_frames, n_plates, 3).
    This function iterates over plates and produces a single DataFrame with all plates
    discriminated by a ``fp_name`` column.

    Args:
        forceplate_data: ForceplateData instance (multi-plate container).
        format: Output format
            - 'wide': One row per (frame, plate) with columns
              [time, frame, fp_name, force_x, …, cop_z]
            - 'long': One row per (frame, plate, variable, axis) with columns
              [time, frame, fp_name, variable, axis, value]
        trial_name: If provided, a 'trial_name' column is added.

    Returns:
        Polars DataFrame in specified format.
    """
    forces = np.asarray(forceplate_data.forces)    # (n_frames, n_plates, 3)
    moments = np.asarray(forceplate_data.moments)  # (n_frames, n_plates, 3)
    cop = np.asarray(forceplate_data.cop)           # (n_frames, n_plates, 3)
    names = forceplate_data.names
    time = np.asarray(forceplate_data.time_vector)
    frames = np.asarray(forceplate_data.frame_vector)
    n_frames = forceplate_data.num_frames

    if format == "wide":
        plate_dfs: list[pl.DataFrame] = []
        for i, fp_name in enumerate(names):
            df_dict: dict[str, Any] = {
                "time": time,
                "frame": frames,
                "fp_name": [fp_name] * n_frames,
                "force_x": forces[:, i, 0],
                "force_y": forces[:, i, 1],
                "force_z": forces[:, i, 2],
                "moment_x": moments[:, i, 0],
                "moment_y": moments[:, i, 1],
                "moment_z": moments[:, i, 2],
                "cop_x": cop[:, i, 0],
                "cop_y": cop[:, i, 1],
                "cop_z": cop[:, i, 2],
            }
            if trial_name is not None:
                df_dict["trial_name"] = [trial_name] * n_frames
            plate_dfs.append(pl.DataFrame(df_dict))

        return pl.concat(plate_dfs)

    elif format == "long":
        plate_dfs = []
        variables = ["force", "force", "force", "moment", "moment", "moment", "cop", "cop", "cop"]
        axes = ["x", "y", "z", "x", "y", "z", "x", "y", "z"]

        for i, fp_name in enumerate(names):
            # Stack per-plate forces/moments/cop into (n_frames, 9)
            all_values = np.column_stack([
                forces[:, i, :], moments[:, i, :], cop[:, i, :]
            ])

            time_repeated = np.repeat(time, 9)
            frame_repeated = np.repeat(frames, 9)

            variable_repeated = np.tile(variables, n_frames)
            axis_repeated = np.tile(axes, n_frames)
            values = all_values.flatten()

            df_dict = {
                "time": time_repeated,
                "frame": frame_repeated,
                "fp_name": [fp_name] * (n_frames * 9),
                "variable": variable_repeated,
                "axis": axis_repeated,
                "value": values,
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
        (and trial_name if provided). Null values for time or frame when not set.
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
