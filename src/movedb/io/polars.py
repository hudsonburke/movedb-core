"""Converters between numpy arrays and Polars DataFrames for biomechanics data."""

import numpy as np
import polars as pl
from typing import Literal
from ..core import MarkerData, AnalogData, ForceplateData


def markers_to_polars(
    marker_data: MarkerData, format: Literal["long", "wide"] = "long"
) -> pl.DataFrame:
    """
    Convert marker data to Polars DataFrame.

    Args:
        marker_data: MarkerData dictionary from HDF5 storage
        format: Output format
            - 'long': One row per (frame, marker) with columns [time, frame, marker_name, x, y, z]
            - 'wide': One row per frame with columns [time, frame, marker1_x, marker1_y, marker1_z, ...]

    Returns:
        Polars DataFrame in specified format

    Example:
        >>> marker_data = trial.load_markers()
        >>> df_long = markers_to_polars(marker_data, format='long')
        >>> # Analyze specific marker
        >>> rasi = df_long.filter(pl.col('marker_name') == 'RASI')
        >>>
        >>> df_wide = markers_to_polars(marker_data, format='wide')
        >>> # Access all markers at once for frame 10
        >>> frame_10 = df_wide.filter(pl.col('frame') == 10)
    """
    data = marker_data.data  # (en_frames, n_markers, 3)
    marker_names = marker_data.marker_names
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

        df_dict = {
            "time": time_repeated,
            "frame": frame_repeated,
            "marker_name": marker_names_repeated,
            "x": xyz_data[:, 0],
            "y": xyz_data[:, 1],
            "z": xyz_data[:, 2],
        }

        # Add residuals if present
        residuals = marker_data.residuals
        if residuals is not None:
            df_dict["residual"] = residuals.flatten()

        return pl.DataFrame(df_dict)

    elif format == "wide":
        # Wide format: one column per marker coordinate
        df_dict = {
            "time": time,
            "frame": frames,
        }

        # Add columns for each marker's x, y, z
        for i, marker_name in enumerate(marker_names):
            df_dict[f"{marker_name}_x"] = data[:, i, 0]
            df_dict[f"{marker_name}_y"] = data[:, i, 1]
            df_dict[f"{marker_name}_z"] = data[:, i, 2]

        # Add residuals if present
        residuals = marker_data.residuals
        if residuals is not None:
            for i, marker_name in enumerate(marker_names):
                df_dict[f"{marker_name}_residual"] = residuals[:, i]

        return pl.DataFrame(df_dict)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def analogs_to_polars(
    analog_data: AnalogData, format: Literal["long", "wide"] = "long"
) -> pl.DataFrame:
    """
    Convert analog data to Polars DataFrame.

    Args:
        analog_data: AnalogData dictionary from HDF5 storage
        format: Output format
            - 'long': One row per (frame, channel) with columns [time, frame, channel_name, value]
            - 'wide': One row per frame with columns [time, frame, channel1, channel2, ...]

    Returns:
        Polars DataFrame in specified format

    Example:
        >>> analog_data = trial.load_analogs()
        >>> df = analogs_to_polars(analog_data, format='wide')
        >>> # Access specific channel
        >>> emg_signal = df.select(['time', 'EMG_biceps'])
    """
    data = analog_data.data  # (n_frames, n_channels)
    channel_names = analog_data.channel_names
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

        return pl.DataFrame(
            {
                "time": time_repeated,
                "frame": frame_repeated,
                "channel_name": channel_names_repeated,
                "value": values,
            }
        )

    elif format == "wide":
        # Wide format: one column per channel
        df_dict = {
            "time": time,
            "frame": frames,
        }

        # Add columns for each channel
        for i, channel_name in enumerate(channel_names):
            df_dict[channel_name] = data[:, i]

        return pl.DataFrame(df_dict)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def forceplate_to_polars(
    forceplate_data: ForceplateData, name: str, format: Literal["long", "wide"] = "wide"
) -> pl.DataFrame:
    """
    Convert force plate data to Polars DataFrame.

    Args:
        forceplate_data: ForceplateData dictionary from HDF5 storage
        name: Name/identifier of the force plate
        format: Output format
            - 'long': One row per (frame, component) with columns [time, frame, variable, axis, value]
            - 'wide': One row per frame with columns [time, frame, force_x, force_y, force_z,
                     moment_x, moment_y, moment_z, cop_x, cop_y, cop_z]

    Returns:
        Polars DataFrame in specified format

    Example:
        >>> fp_data = trial.load_forceplate('FP1')
        >>> df = forceplate_to_polars(fp_data, name='FP1', format='wide')
        >>> # Calculate resultant force
        >>> df = df.with_columns(
        ...     force_resultant=(
        ...         pl.col('force_x')**2 + pl.col('force_y')**2 + pl.col('force_z')**2
        ...     ).sqrt()
        ... )
    """
    forces = forceplate_data.forces  # (n_frames, 3)
    moments = forceplate_data.moments  # (n_frames, 3)
    cop = forceplate_data.cop  # (n_frames, 3)
    rate = forceplate_data.rate

    n_frames = forces.shape[0]
    time = np.arange(n_frames) / rate
    frames = np.arange(n_frames)

    if format == "wide":
        return pl.DataFrame(
            {
                "time": time,
                "frame": frames,
                "fp_name": [name] * n_frames,
                "force_x": forces[:, 0],
                "force_y": forces[:, 1],
                "force_z": forces[:, 2],
                "moment_x": moments[:, 0],
                "moment_y": moments[:, 1],
                "moment_z": moments[:, 2],
                "cop_x": cop[:, 0],
                "cop_y": cop[:, 1],
                "cop_z": cop[:, 2],
            }
        )

    elif format == "long":
        # Long format: one row per (frame, variable, axis)
        # Stack all variables
        time_repeated = np.repeat(time, 9)  # 3 variables * 3 axes
        frame_repeated = np.repeat(frames, 9)
        fp_name_repeated = [name] * (n_frames * 9)

        # Create variable and axis labels
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

        variable_repeated = np.tile(variables, n_frames)
        axis_repeated = np.tile(axes, n_frames)

        # Stack all values
        all_values = np.column_stack([forces, moments, cop])  # (n_frames, 9)
        values = all_values.flatten()

        return pl.DataFrame(
            {
                "time": time_repeated,
                "frame": frame_repeated,
                "fp_name": fp_name_repeated,
                "variable": variable_repeated,
                "axis": axis_repeated,
                "value": values,
            }
        )

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def forceplates_to_polars(
    forceplates_data: dict[str, ForceplateData],
    format: Literal["long", "wide"] = "wide",
) -> pl.DataFrame:
    """
    Convert multiple force plate data to a single Polars DataFrame.

    Args:
        forceplates_data: Dictionary mapping force plate names to ForceplateData
        format: Output format ('long' or 'wide')

    Returns:
        Combined Polars DataFrame with all force plates

    Example:
        >>> all_fp = trial.load_all_forceplates()
        >>> df = forceplates_to_polars(all_fp, format='wide')
        >>> # Filter to specific force plate
        >>> fp1 = df.filter(pl.col('fp_name') == 'FP1')
    """
    dfs = []
    for name, fp_data in forceplates_data.items():
        df = forceplate_to_polars(fp_data, name=name, format=format)
        dfs.append(df)

    if not dfs:
        return pl.DataFrame()

    return pl.concat(dfs)
