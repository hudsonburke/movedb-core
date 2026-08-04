"""Compute and persist selection metrics inside the DuckDB catalog."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from .protocols import CatalogConnection


def refresh_selection_metrics(
    conn: CatalogConnection,
    *,
    session_metrics_rows: list[dict[str, object]],
    trial_metrics_rows: list[dict[str, object]],
) -> None:
    conn.execute("DELETE FROM movedb_catalog.session_metrics")
    conn.execute("DELETE FROM movedb_catalog.trial_metrics")

    if session_metrics_rows:
        session_df = pl.DataFrame(session_metrics_rows)
        conn.register("session_metrics_df", session_df.to_arrow())
        conn.execute(
            "INSERT INTO movedb_catalog.session_metrics SELECT * FROM session_metrics_df"
        )

    if trial_metrics_rows:
        trial_df = pl.DataFrame(trial_metrics_rows)
        conn.register("trial_metrics_df", trial_df.to_arrow())
        conn.execute(
            "INSERT INTO movedb_catalog.trial_metrics SELECT * FROM trial_metrics_df"
        )


def load_raw_parameters_json(motion_dir: Path) -> dict[str, object] | None:
    params_path = motion_dir / "parameters.json"
    if not params_path.exists():
        return None
    try:
        return json.loads(params_path.read_text())
    except Exception:
        return None
