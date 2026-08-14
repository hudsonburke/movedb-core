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


def process_session(
    subject_id: str,
    session: str,
    c3d_files: Sequence[str | Path],
    output_dir: str | Path,
) -> dict[str, pl.DataFrame]:
    """Convert a session's C3D files to Parquet.

    Also extracts PROCESSING parameters (mass, bone lengths) from C3D files
    and writes them to parameters.parquet for use in model scaling.
    """
    from .adapters.c3d import read_markers, read_forceplates, read_events, read_parameters

    output_dir = Path(output_dir)
    subject_dir = output_dir / subject_id
    subject_dir.mkdir(parents=True, exist_ok=True)

    all_markers = []
    all_forceplates = []
    all_events = []
    all_params = []

    for c3d_path in c3d_files:
        c3d_path = Path(c3d_path)
        trial_name = c3d_path.stem

        try:
            # Extract markers
            markers_df = read_markers(c3d_path, trial_name)
            markers_df = markers_df.with_columns([
                pl.lit(subject_id).alias("subject_id"),
                pl.lit(session).alias("session_id"),
            ])
            markers_df = _ensure_string_types(markers_df)
            all_markers.append(markers_df)

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

            # Extract events
            events_df = read_events(c3d_path, trial_name)
            events_df = events_df.with_columns([
                pl.lit(subject_id).alias("subject_id"),
                pl.lit(session).alias("session_id"),
            ])
            events_df = _ensure_string_types(events_df)
            if not events_df.is_empty():
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
    if all_markers:
        result["markers"] = pl.concat(all_markers, how="diagonal")
        markers_path = subject_dir / "markers.parquet"
        if markers_path.exists():
            existing = pl.read_parquet(markers_path)
            result["markers"] = pl.concat([existing, result["markers"]], how="diagonal")
        result["markers"].write_parquet(markers_path)
        logger.info(f"  {subject_id}/{session}: {len(result['markers'])} marker rows")

    if all_forceplates:
        fp_df = pl.concat(all_forceplates, how="diagonal")

        result["forceplates"] = fp_df
        fp_path = subject_dir / "forceplates.parquet"
        if fp_path.exists():
            existing = pl.read_parquet(fp_path)
            result["forceplates"] = pl.concat([existing, result["forceplates"]], how="diagonal")
        result["forceplates"].write_parquet(fp_path)
        logger.info(f"  {subject_id}/{session}: {len(result['forceplates'])} forceplate rows")

    if all_events:
        result["events"] = pl.concat(all_events, how="diagonal")
        events_path = subject_dir / "events.parquet"
        if events_path.exists():
            existing = pl.read_parquet(events_path)
            result["events"] = pl.concat([existing, result["events"]], how="diagonal")
        result["events"].write_parquet(events_path)
        logger.info(f"  {subject_id}/{session}: {len(result['events'])} events")

    # Write parameters.parquet
    if all_params:
        params_df = pl.DataFrame(all_params)
        params_df = _ensure_string_types(params_df)

        params_path = subject_dir / "parameters.parquet"

        if params_path.exists():
            existing = pl.read_parquet(params_path)
            # Drop rows we're about to replace (matched by all three keys)
            new_keys = params_df.select("trial_name", "subject_id", "session_id")
            existing = existing.join(new_keys, on=["trial_name", "subject_id", "session_id"], how="anti")
            params_df = pl.concat([existing, params_df], how="diagonal")

        params_df.write_parquet(params_path)
        result["parameters"] = params_df
        logger.info(f"  {subject_id}/{session}: {len(all_params)} trial parameters extracted")

    return result
