"""Helpers for persisting selection and quality results into the catalog."""

from __future__ import annotations

import json
from typing import Any

import polars as pl

from .protocols import CatalogConnection
from .views import create_catalog_views


# Canonical column order per table — used to build DataFrames with the
# exact schema DuckDB expects.
_SESSION_QUALITY_COLUMNS = [
    "session_key", "session_dir", "subject_id", "session_id",
    "qualifies_for_osim", "static_trial", "reason", "motion_dir",
    "opensim_dir", "mass_kg", "right_femur_length_mm", "left_femur_length_mm",
    "right_tibia_length_mm", "left_tibia_length_mm", "right_foot_length_mm",
    "left_foot_length_mm", "metadata_json",
]

_TRIAL_QUALITY_COLUMNS = [
    "trial_key", "session_key", "subject_id", "session_id", "trial_name",
    "qualifies_for_ik", "qualifies_for_id", "reason", "t_start", "t_end",
    "motion_dir", "opensim_dir", "has_fp_mapping", "fp_mapping",
    "enf_notes", "metadata_json",
]

_SESSION_QUALITY_SCHEMA = {
    "session_key": pl.Utf8, "session_dir": pl.Utf8, "subject_id": pl.Utf8,
    "session_id": pl.Utf8, "qualifies_for_osim": pl.Boolean,
    "static_trial": pl.Utf8, "reason": pl.Utf8, "motion_dir": pl.Utf8,
    "opensim_dir": pl.Utf8, "mass_kg": pl.Float64,
    "right_femur_length_mm": pl.Float64, "left_femur_length_mm": pl.Float64,
    "right_tibia_length_mm": pl.Float64, "left_tibia_length_mm": pl.Float64,
    "right_foot_length_mm": pl.Float64, "left_foot_length_mm": pl.Float64,
    "metadata_json": pl.Utf8,
}

_TRIAL_QUALITY_SCHEMA = {
    "trial_key": pl.Utf8, "session_key": pl.Utf8, "subject_id": pl.Utf8,
    "session_id": pl.Utf8, "trial_name": pl.Utf8,
    "qualifies_for_ik": pl.Boolean, "qualifies_for_id": pl.Boolean,
    "reason": pl.Utf8, "t_start": pl.Float64, "t_end": pl.Float64,
    "motion_dir": pl.Utf8, "opensim_dir": pl.Utf8,
    "has_fp_mapping": pl.Boolean, "fp_mapping": pl.Utf8,
    "enf_notes": pl.Utf8, "metadata_json": pl.Utf8,
}


def write_session_quality(conn: CatalogConnection, rows: list[dict[str, Any]]) -> None:
    """Replace session-quality rows in the catalog."""

    conn.execute("DELETE FROM movedb_catalog.session_quality")
    if not rows:
        return
    rows = [_prepare_row(r, _SESSION_QUALITY_COLUMNS) for r in rows]
    df = pl.DataFrame(rows, schema=_SESSION_QUALITY_SCHEMA, orient="row")
    conn.register("_sq_df", df.to_arrow())
    conn.execute(
        "INSERT INTO movedb_catalog.session_quality SELECT * FROM _sq_df"
    )
    create_catalog_views(conn)


def write_trial_quality(conn: CatalogConnection, rows: list[dict[str, Any]]) -> None:
    """Replace trial-quality rows in the catalog."""

    conn.execute("DELETE FROM movedb_catalog.trial_quality")
    if not rows:
        return
    rows = [_prepare_row(r, _TRIAL_QUALITY_COLUMNS) for r in rows]
    df = pl.DataFrame(rows, schema=_TRIAL_QUALITY_SCHEMA, orient="row")
    conn.register("_tq_df", df.to_arrow())
    conn.execute(
        "INSERT INTO movedb_catalog.trial_quality SELECT * FROM _tq_df"
    )
    create_catalog_views(conn)


def _prepare_row(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    """Return a flat row with metadata_json injected from extra keys."""
    known = set(columns) - {"metadata_json"}
    metadata = {k: v for k, v in row.items() if k not in known}
    out = {col: row.get(col) for col in known}
    out["metadata_json"] = json.dumps(metadata, sort_keys=True) if metadata else None
    return out
