"""Converters between core models, Polars DataFrames, and Parquet files."""

import numpy as np
import polars as pl
from typing import Any, Literal
from ..core import (
    AnalogData,
    Event,
    ForceplateData,
    GRFData,
    KinematicsData,
    MarkerData,
)

# TODO: Optimize wide/long conversions and add projection helpers


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
    free_moment = (
        np.asarray(forceplate_data.free_moment)
        if forceplate_data.free_moment is not None
        else None
    )  # (n_frames, n_plates, 3) or None
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
        # FP_name -> Struct({force: Struct({x,y,z}), moment: ..., cop: ..., [free_moment: ...]})
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

            struct_fields = [force_struct, moment_struct, cop_struct]

            if free_moment is not None:
                free_moment_struct = pl.struct(
                    pl.Series("x", free_moment[:, i, 0]),
                    pl.Series("y", free_moment[:, i, 1]),
                    pl.Series("z", free_moment[:, i, 2]),
                ).alias("free_moment")
                struct_fields.append(free_moment_struct)

            plate_cols.append(pl.struct(*struct_fields).alias(fp_name))

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

        if free_moment is not None:
            variables += ["free_moment", "free_moment", "free_moment"]
            axes += ["x", "y", "z"]

        n_vars = len(variables)

        plate_dfs: list[pl.DataFrame] = []
        for i, fp_name in enumerate(names):
            cols = [
                forces[:, i, :],
                moments[:, i, :],
                cop[:, i, :],
            ]
            if free_moment is not None:
                cols.append(free_moment[:, i, :])

            all_values = np.column_stack(cols)  # (n_frames, n_vars)

            time_repeated = np.repeat(time, n_vars)
            frame_repeated = np.repeat(frames, n_vars)

            df_dict: dict[str, Any] = {
                "time": time_repeated,
                "frame": frame_repeated,
                "fp_name": [fp_name] * (n_frames * n_vars),
                "variable": np.tile(variables, n_frames),
                "axis": np.tile(axes, n_frames),
                "value": all_values.flatten(),
            }
            if trial_name is not None:
                df_dict["trial_name"] = [trial_name] * (n_frames * n_vars)
            plate_dfs.append(pl.DataFrame(df_dict))

        return pl.concat(plate_dfs, how="diagonal")

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


def kinematics_to_polars(
    kinematics: KinematicsData,
    format: Literal["long", "wide"] = "wide",
    trial_name: str | None = None,
) -> pl.DataFrame:
    """Convert joint kinematics to a Polars DataFrame.

    Args:
        kinematics: ``KinematicsData`` instance.
        format:
            - ``"wide"`` — one row per frame, one struct column per DOF
              with fields ``{pos, vel, acc, tau}`` and optional mask fields.
            - ``"long"`` — one row per ``(frame, dof)`` with flat columns
              ``[time, frame, dof_name, pos, vel, acc, tau]``.
        trial_name: If provided, a ``trial_name`` column is added.
    """
    pos = np.asarray(kinematics.pos)   # (n_frames, n_dofs)
    vel = np.asarray(kinematics.vel)
    acc = np.asarray(kinematics.acc)
    tau = np.asarray(kinematics.tau)
    dof_names = kinematics.names

    n_frames, n_dofs = pos.shape
    rate = kinematics.rate
    first_frame = kinematics.first_frame

    time = np.arange(n_frames) / rate
    frames = np.arange(first_frame, first_frame + n_frames)

    has_masks = (
        kinematics.pos_observed is not None
        and kinematics.vel_finite_differenced is not None
        and kinematics.acc_finite_differenced is not None
    )
    if has_masks:
        pos_obs = np.asarray(kinematics.pos_observed)
        vel_fd = np.asarray(kinematics.vel_finite_differenced)
        acc_fd = np.asarray(kinematics.acc_finite_differenced)

    if format == "wide":
        base_dict: dict[str, Any] = {"time": time, "frame": frames}
        if trial_name is not None:
            base_dict["trial_name"] = [trial_name] * n_frames
        df = pl.DataFrame(base_dict)

        struct_cols = []
        for i, name in enumerate(dof_names):
            fields = [
                pl.Series("pos", pos[:, i]),
                pl.Series("vel", vel[:, i]),
                pl.Series("acc", acc[:, i]),
                pl.Series("tau", tau[:, i]),
            ]
            if has_masks:
                fields.append(pl.Series("pos_observed", pos_obs[:, i]))
                fields.append(pl.Series("vel_finite_differenced", vel_fd[:, i]))
                fields.append(pl.Series("acc_finite_differenced", acc_fd[:, i]))
            struct_cols.append(pl.struct(fields).alias(name))

        return df.with_columns(struct_cols)

    elif format == "long":
        time_repeated = np.repeat(time, n_dofs)
        frame_repeated = np.repeat(frames, n_dofs)
        dof_repeated = np.tile(dof_names, n_frames)

        df_dict: dict[str, Any] = {
            "time": time_repeated,
            "frame": frame_repeated,
            "dof_name": dof_repeated,
            "pos": pos.flatten(),
            "vel": vel.flatten(),
            "acc": acc.flatten(),
            "tau": tau.flatten(),
        }
        if trial_name is not None:
            df_dict["trial_name"] = [trial_name] * len(time_repeated)
        if has_masks:
            df_dict["pos_observed"] = pos_obs.flatten()
            df_dict["vel_finite_differenced"] = vel_fd.flatten()
            df_dict["acc_finite_differenced"] = acc_fd.flatten()

        return pl.DataFrame(df_dict)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")


def grf_to_polars(
    grf: GRFData,
    format: Literal["long", "wide"] = "wide",
    trial_name: str | None = None,
) -> pl.DataFrame:
    """Convert ground reaction force data to a Polars DataFrame.

    Args:
        grf: ``GRFData`` instance.
        format:
            - ``"wide"`` — one row per frame, one struct column per body
              with fields ``{fx, fy, fz, copx, copy, copz, tx, ty, tz}``
              and optional root-frame + contact fields.
            - ``"long"`` — one row per ``(frame, body)`` with flat columns.
        trial_name: If provided, a ``trial_name`` column is added.
    """
    force = np.asarray(grf.force)   # (n_frames, n_bodies, 3)
    cop = np.asarray(grf.cop)
    torque = np.asarray(grf.torque)
    body_names = grf.names

    n_frames, n_bodies, _ = force.shape
    rate = grf.rate
    first_frame = grf.first_frame

    time = np.arange(n_frames) / rate
    frames = np.arange(first_frame, first_frame + n_frames)

    has_root = (
        grf.force_root is not None
        and grf.cop_root is not None
        and grf.torque_root is not None
    )
    if has_root:
        force_root = np.asarray(grf.force_root)
        cop_root = np.asarray(grf.cop_root)
        torque_root = np.asarray(grf.torque_root)

    has_contact = grf.contact is not None
    if has_contact:
        contact = np.asarray(grf.contact)

    if format == "wide":
        base_dict: dict[str, Any] = {"time": time, "frame": frames}
        if trial_name is not None:
            base_dict["trial_name"] = [trial_name] * n_frames
        df = pl.DataFrame(base_dict)

        struct_cols = []
        for i, name in enumerate(body_names):
            fields = [
                pl.Series("fx", force[:, i, 0]),
                pl.Series("fy", force[:, i, 1]),
                pl.Series("fz", force[:, i, 2]),
                pl.Series("copx", cop[:, i, 0]),
                pl.Series("copy", cop[:, i, 1]),
                pl.Series("copz", cop[:, i, 2]),
                pl.Series("tx", torque[:, i, 0]),
                pl.Series("ty", torque[:, i, 1]),
                pl.Series("tz", torque[:, i, 2]),
            ]
            if has_root:
                fields.extend([
                    pl.Series("fx_root", force_root[:, i, 0]),
                    pl.Series("fy_root", force_root[:, i, 1]),
                    pl.Series("fz_root", force_root[:, i, 2]),
                    pl.Series("copx_root", cop_root[:, i, 0]),
                    pl.Series("copy_root", cop_root[:, i, 1]),
                    pl.Series("copz_root", cop_root[:, i, 2]),
                    pl.Series("tx_root", torque_root[:, i, 0]),
                    pl.Series("ty_root", torque_root[:, i, 1]),
                    pl.Series("tz_root", torque_root[:, i, 2]),
                ])
            if has_contact:
                fields.append(pl.Series("contact", contact[:, i]))
            struct_cols.append(pl.struct(fields).alias(name))

        return df.with_columns(struct_cols)

    elif format == "long":
        time_repeated = np.repeat(time, n_bodies)
        frame_repeated = np.repeat(frames, n_bodies)
        body_repeated = np.tile(body_names, n_frames)

        df_dict: dict[str, Any] = {
            "time": time_repeated,
            "frame": frame_repeated,
            "body_name": body_repeated,
            "fx": force[:, :, 0].flatten(),
            "fy": force[:, :, 1].flatten(),
            "fz": force[:, :, 2].flatten(),
            "copx": cop[:, :, 0].flatten(),
            "copy": cop[:, :, 1].flatten(),
            "copz": cop[:, :, 2].flatten(),
            "tx": torque[:, :, 0].flatten(),
            "ty": torque[:, :, 1].flatten(),
            "tz": torque[:, :, 2].flatten(),
        }
        if trial_name is not None:
            df_dict["trial_name"] = [trial_name] * len(time_repeated)
        if has_root:
            df_dict["fx_root"] = force_root[:, :, 0].flatten()
            df_dict["fy_root"] = force_root[:, :, 1].flatten()
            df_dict["fz_root"] = force_root[:, :, 2].flatten()
            df_dict["copx_root"] = cop_root[:, :, 0].flatten()
            df_dict["copy_root"] = cop_root[:, :, 1].flatten()
            df_dict["copz_root"] = cop_root[:, :, 2].flatten()
            df_dict["tx_root"] = torque_root[:, :, 0].flatten()
            df_dict["ty_root"] = torque_root[:, :, 1].flatten()
            df_dict["tz_root"] = torque_root[:, :, 2].flatten()
        if has_contact:
            df_dict["contact"] = contact.flatten()

        return pl.DataFrame(df_dict)

    else:
        raise ValueError(f"Unknown format: {format}. Use 'long' or 'wide'.")
