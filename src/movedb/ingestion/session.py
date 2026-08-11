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


def extract_session_params(c3d_path: Path) -> dict[str, float | str]:
    """Extract all PROCESSING parameters from a C3D file."""
    import ezc3d

    c3d = ezc3d.c3d(str(c3d_path))

    params = {}
    if "PROCESSING" not in c3d.parameters:
        return params

    for param_name, param_info in c3d.parameters["PROCESSING"].items():
        value = param_info.get("value")
        if value and len(value) > 0:
            val = value[0]
            if val is None:
                continue
            try:
                params[param_name] = float(val)
            except (ValueError, TypeError):
                params[param_name] = str(val)

    return params


def process_session(
    subject_id: str,
    session: str,
    c3d_files: list[str | Path],
    output_dir: str | Path,
) -> dict[str, pl.DataFrame]:
    """Convert a session's C3D files to Parquet.

    Also extracts PROCESSING parameters (mass, bone lengths) from C3D files
    and writes them to sessions.parquet for use in model scaling.
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
    all_session_params = []

    for c3d_path in c3d_files:
        c3d_path = Path(c3d_path)
        trial_name = c3d_path.stem

        try:
            c3d = ezc3d.c3d(str(c3d_path), extract_forceplat_data=True)

            # Extract markers
            marker_data = extract_markers(c3d)
            markers_df = markers_to_polars(marker_data, format="long", trial_name=trial_name)
            markers_df = markers_df.with_columns([
                pl.lit(subject_id).alias("subject_id"),
                pl.lit(session).alias("session_id"),
            ])
            markers_df = _ensure_string_types(markers_df)
            all_markers.append(markers_df)

            # Extract force plates
            try:
                fp_data = extract_forceplates(c3d)
                fp_df = forceplates_to_polars(fp_data, format="long", trial_name=trial_name)
                fp_df = fp_df.with_columns([
                    pl.lit(subject_id).alias("subject_id"),
                    pl.lit(session).alias("session_id"),
                ])
                fp_df = _ensure_string_types(fp_df)
                all_forceplates.append(fp_df)
            except (ValueError, KeyError) as e:
                logger.debug(f"  {trial_name}: no force plate data: {e}")

            # Extract events
            events = extract_events(c3d)
            events_df = events_to_polars(events, trial_name=trial_name)
            events_df = events_df.with_columns([
                pl.lit(subject_id).alias("subject_id"),
                pl.lit(session).alias("session_id"),
            ])
            events_df = _ensure_string_types(events_df)
            if not events_df.is_empty():
                all_events.append(events_df)

            # Extract session parameters
            session_params = extract_session_params(c3d_path)
            if session_params:
                session_params["subject_id"] = subject_id
                session_params["session_id"] = session
                all_session_params.append(session_params)

        except Exception as e:
            logger.warning(f"  Failed to process {c3d_path}: {e}")
            continue

    # Write Parquet files
    result = {}
    if all_markers:
        result["markers"] = pl.concat(all_markers, how="diagonal")
        result["markers"].write_parquet(subject_dir / "markers.parquet")
        logger.info(f"  {subject_id}/{session}: {len(result['markers'])} marker rows")

    if all_forceplates:
        result["forceplates"] = pl.concat(all_forceplates, how="diagonal")
        result["forceplates"].write_parquet(subject_dir / "forceplates.parquet")
        logger.info(f"  {subject_id}/{session}: {len(result['forceplates'])} forceplate rows")

    if all_events:
        result["events"] = pl.concat(all_events, how="diagonal")
        result["events"].write_parquet(subject_dir / "events.parquet")
        logger.info(f"  {subject_id}/{session}: {len(result['events'])} events")

    # Write sessions.parquet
    if all_session_params:
        seen = set()
        unique_params = []
        for params in all_session_params:
            key = (params.get("subject_id"), params.get("session_id"))
            if key not in seen:
                seen.add(key)
                unique_params.append(params)

        sessions_df = pl.DataFrame(unique_params)
        sessions_df = _ensure_string_types(sessions_df)

        sessions_path = subject_dir / "sessions.parquet"

        if sessions_path.exists():
            existing = pl.read_parquet(sessions_path)

            old_session = existing.filter(
                (pl.col("subject_id") == subject_id) & (pl.col("session_id") == session)
            )
            if not old_session.is_empty():
                for col in sessions_df.columns:
                    if col in ("subject_id", "session_id"):
                        continue
                    if col in old_session.columns:
                        old_val = old_session[col][0]
                        new_val = sessions_df[col][0]
                        if old_val != new_val:
                            logger.warning(
                                f"Parameter {col} differs for {subject_id}/{session}: "
                                f"{old_val} vs {new_val}"
                            )

            existing = existing.filter(
                ~((pl.col("subject_id") == subject_id) & (pl.col("session_id") == session))
            )
            sessions_df = pl.concat([existing, sessions_df], how="diagonal")

        sessions_df.write_parquet(sessions_path)
        result["sessions"] = sessions_df
        logger.info(f"  {subject_id}/{session}: sessions parameters extracted")

    return result
