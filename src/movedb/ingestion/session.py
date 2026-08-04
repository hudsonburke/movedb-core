"""Session-level C3D to Parquet conversion.

This module provides the core ingestion function for converting a session's
C3D files into Parquet.  Directory discovery and subject/session naming
conventions are application-specific and left to the caller.
"""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


def process_session(
    subject_id: str,
    session: str,
    c3d_files: list[str | Path],
    output_dir: str | Path,
) -> dict[str, pl.DataFrame]:
    """Convert a session's C3D files to Parquet.

    Reads C3D files using movedb-core's adapters, converts to Polars
    DataFrames using the polars adapter, and writes Parquet files.

    Parameters
    ----------
    subject_id : str
        Subject identifier (e.g. "BAA01").
    session : str
        Session name (e.g. "Baseline", "Week24").
    c3d_files : list[str | Path]
        List of C3D file paths for this session.
    output_dir : str | Path
        Output directory.  Parquet files are written to
        ``{output_dir}/{subject_id}/``.

    Returns
    -------
    dict[str, pl.DataFrame]
        Dict mapping data type to DataFrame ("markers", "forceplates", "events").
    """
    from ..adapters.c3d import extract_markers, extract_forceplates, extract_events
    from ..adapters.polars import markers_to_polars, forceplates_to_polars, events_to_polars
    import ezc3d

    output_dir = Path(output_dir)
    subject_dir = output_dir / subject_id
    subject_dir.mkdir(parents=True, exist_ok=True)

    all_markers = []
    all_forceplates = []
    all_events = []

    for c3d_path in c3d_files:
        c3d_path = Path(c3d_path)
        trial_name = c3d_path.stem

        try:
            c3d = ezc3d.c3d(str(c3d_path))

            # Extract + convert using movedb-core adapters
            marker_data = extract_markers(c3d)
            markers_df = markers_to_polars(marker_data, trial_name=trial_name)
            markers_df = markers_df.with_columns([
                pl.lit(subject_id).alias("subject_id"),
                pl.lit(session).alias("session_id"),
            ])
            all_markers.append(markers_df)

            fp_data = extract_forceplates(c3d)
            fp_df = forceplates_to_polars(fp_data, trial_name=trial_name)
            fp_df = fp_df.with_columns([
                pl.lit(subject_id).alias("subject_id"),
                pl.lit(session).alias("session_id"),
            ])
            all_forceplates.append(fp_df)

            events = extract_events(c3d)
            events_df = events_to_polars(events, trial_name=trial_name)
            events_df = events_df.with_columns([
                pl.lit(subject_id).alias("subject_id"),
                pl.lit(session).alias("session_id"),
            ])
            if not events_df.is_empty():
                all_events.append(events_df)

        except Exception as e:
            logger.warning(f"  Failed to process {c3d_path}: {e}")
            continue

    # Write Parquet files
    result = {}
    if all_markers:
        result["markers"] = pl.concat(all_markers)
        result["markers"].write_parquet(subject_dir / "markers.parquet")
        logger.info(f"  {subject_id}/{session}: {len(result['markers'])} marker rows")

    if all_forceplates:
        result["forceplates"] = pl.concat(all_forceplates)
        result["forceplates"].write_parquet(subject_dir / "forceplates.parquet")
        logger.info(f"  {subject_id}/{session}: {len(result['forceplates'])} forceplate rows")

    if all_events:
        result["events"] = pl.concat(all_events)
        result["events"].write_parquet(subject_dir / "events.parquet")
        logger.info(f"  {subject_id}/{session}: {len(result['events'])} events")

    return result
