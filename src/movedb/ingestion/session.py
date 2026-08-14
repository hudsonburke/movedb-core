"""Session-level C3D to Parquet conversion.

This module provides the core ingestion function for converting a session's
C3D files into Parquet.  Directory discovery and subject/session naming
conventions are application-specific and left to the caller.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

# Columns that should always be String type (some C3D files have numeric names)
STRING_COLUMNS = ["marker_name", "trial_name", "subject_id", "session_id", "context", "label"]


def _ensure_string_types(df: pl.DataFrame) -> pl.DataFrame:
    """Cast known string columns to Utf8 type to prevent type mismatches."""
    casts = []
    for col in df.columns:
        if col in STRING_COLUMNS and df[col].dtype != pl.Utf8:
            casts.append(pl.col(col).cast(pl.Utf8))
    if casts:
        df = df.with_columns(casts)
    return df


def _write_parquet(
    df: pl.DataFrame,
    path: Path,
    result: dict[str, pl.DataFrame],
    key: str,
    log_msg: str,
) -> None:
    """Concat with existing parquet if present, then write."""
    if path.exists():
        existing = pl.read_parquet(path)
        df = pl.concat([existing, df], how="diagonal")
    df.write_parquet(path)
    result[key] = df
    logger.info(log_msg)


def process_session(
    subject_id: str,
    session: str,
    c3d_files: Sequence[str | Path],
    output_dir: str | Path,
) -> dict[str, pl.DataFrame]:
    """Convert a session's C3D files to Parquet.

    Extracts points, force plates, force plate geometry, analogs,
    events, and parameters from each C3D file and writes them to
    Parquet files in the output directory.
    """
    from .adapters.c3d import (
        read_analogs,
        read_events,
        read_forceplate_geometry,
        read_forceplates,
        read_parameters,
        read_points,
    )

    output_dir = Path(output_dir)
    subject_dir = output_dir / subject_id
    subject_dir.mkdir(parents=True, exist_ok=True)

    all_points = []
    all_forceplates = []
    all_fp_geometry = []
    all_analogs = []
    all_events = []
    all_params = []

    for c3d_path in c3d_files:
        c3d_path = Path(c3d_path)
        trial_name = c3d_path.stem

        try:
            # Extract points
            points_df = read_points(c3d_path, trial_name)
            points_df = points_df.with_columns([
                pl.lit(subject_id).alias("subject_id"),
                pl.lit(session).alias("session_id"),
            ])
            points_df = _ensure_string_types(points_df)
            all_points.append(points_df)

            # Extract force plates
            try:
                fp_df = read_forceplates(c3d_path, trial_name)
                fp_df = fp_df.with_columns([
                    pl.lit(subject_id).alias("subject_id"),
                    pl.lit(session).alias("session_id"),
                ])
                fp_df = _ensure_string_types(fp_df)
                all_forceplates.append(fp_df)
            except (ValueError, KeyError) as e:
                logger.debug(f"  {trial_name}: no force plate data: {e}")

            # Extract force plate geometry
            try:
                fp_geom_df = read_forceplate_geometry(c3d_path, trial_name)
                if not fp_geom_df.is_empty():
                    fp_geom_df = fp_geom_df.with_columns([
                        pl.lit(subject_id).alias("subject_id"),
                        pl.lit(session).alias("session_id"),
                    ])
                    all_fp_geometry.append(fp_geom_df)
            except (ValueError, KeyError) as e:
                logger.debug(f"  {trial_name}: no force plate geometry: {e}")

            # Extract analogs
            try:
                analogs_df = read_analogs(c3d_path, trial_name)
                if not analogs_df.is_empty():
                    analogs_df = analogs_df.with_columns([
                        pl.lit(subject_id).alias("subject_id"),
                        pl.lit(session).alias("session_id"),
                    ])
                    analogs_df = _ensure_string_types(analogs_df)
                    all_analogs.append(analogs_df)
            except (ValueError, KeyError) as e:
                logger.debug(f"  {trial_name}: no analog data: {e}")

            # Extract events
            events_df = read_events(c3d_path, trial_name)
            if not events_df.is_empty():
                events_df = events_df.with_columns([
                    pl.lit(subject_id).alias("subject_id"),
                    pl.lit(session).alias("session_id"),
                ])
                events_df = _ensure_string_types(events_df)
                all_events.append(events_df)

            # Extract trial parameters
            trial_params = read_parameters(c3d_path)
            if trial_params:
                trial_params["trial_name"] = trial_name
                trial_params["subject_id"] = subject_id
                trial_params["session_id"] = session
                all_params.append(trial_params)

        except Exception as e:
            logger.warning(f"  Failed to process {c3d_path}: {e}")
            continue

    # Write Parquet files
    result = {}

    if all_points:
        df = pl.concat(all_points, how="diagonal")
        _write_parquet(
            df,
            subject_dir / "points.parquet",
            result,
            "points",
            f"  {subject_id}/{session}: {len(df)} point rows",
        )

    if all_forceplates:
        df = pl.concat(all_forceplates, how="diagonal")
        _write_parquet(
            df,
            subject_dir / "forceplates.parquet",
            result,
            "forceplates",
            f"  {subject_id}/{session}: {len(df)} forceplate rows",
        )

    if all_fp_geometry:
        df = pl.concat(all_fp_geometry, how="diagonal")
        _write_parquet(
            df,
            subject_dir / "forceplate_geometry.parquet",
            result,
            "forceplate_geometry",
            f"  {subject_id}/{session}: {len(df)} forceplate geometry rows",
        )

    if all_analogs:
        df = pl.concat(all_analogs, how="diagonal")
        _write_parquet(
            df,
            subject_dir / "analogs.parquet",
            result,
            "analogs",
            f"  {subject_id}/{session}: {len(df)} analog rows",
        )

    if all_events:
        df = pl.concat(all_events, how="diagonal")
        _write_parquet(
            df,
            subject_dir / "events.parquet",
            result,
            "events",
            f"  {subject_id}/{session}: {len(df)} event rows",
        )

    if all_params:
        df = pl.DataFrame(all_params)
        df = _ensure_string_types(df)

        params_path = subject_dir / "parameters.parquet"
        if params_path.exists():
            existing = pl.read_parquet(params_path)
            new_keys = df.select("trial_name", "subject_id", "session_id")
            existing = existing.join(new_keys, on=["trial_name", "subject_id", "session_id"], how="anti")
            df = pl.concat([existing, df], how="diagonal")

        df.write_parquet(params_path)
        result["parameters"] = df
        logger.info(f"  {subject_id}/{session}: {len(all_params)} trial parameters extracted")

    return result
