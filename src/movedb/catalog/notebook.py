"""Notebook-friendly DuckDB helpers for dataset and scratch workflows.

These helpers support a DuckDB-first interactive workflow:

- select subjects, sessions, and trials from a root-level catalog
- inspect session/trial qualification state from DuckDB tables and views
- register scratch outputs as temporary DuckDB views during a notebook session
- compare canonical catalog state with in-notebook experimental outputs

Typical usage in a project notebook looks like:

```python
from pathlib import Path
from movedb.catalog import (
    connect_workbench_catalog,
    sql_list_subjects,
    sql_list_sessions,
    sql_list_trials,
    register_scratch_views,
)

conn = connect_workbench_catalog(Path("catalog.duckdb"), read_only=False)
subjects = sql_list_subjects(conn, where="s.qualifies_for_osim = TRUE")
sessions = sql_list_sessions(conn, subject_id="sub-a02")
trials = sql_list_trials(conn, subject_id="sub-a02", session_id="ses-baseline")
```

Project repositories should typically keep execution logic and plotting local,
while reusing these helpers for catalog-driven notebook selection and scratch
inspection.
"""

from __future__ import annotations

from pathlib import Path

from duckdb import connect
import polars as pl

from .protocols import CatalogConnection


def connect_workbench_catalog(
    catalog_path: Path,
    *,
    read_only: bool = False,
) -> CatalogConnection:
    """Open a DuckDB catalog connection for interactive notebook use."""

    return connect(str(catalog_path), read_only=read_only)


def sql_list_subjects(
    conn: CatalogConnection,
    where: str | None = None,
) -> pl.DataFrame:
    """Return one row per subject with trial counts.

    The optional `where` predicate is appended directly to the SQL query and is
    intended to reference the aliases `s` (session metrics) and `t` (trial
    metrics).
    """

    sql = """
        SELECT
            s.subject_id,
            count(*) AS n_trials,
            count(*) FILTER (WHERE t.qualifies_for_id) AS n_id_trials
        FROM movedb_catalog.trial_selection_metrics AS t
        JOIN movedb_catalog.session_selection_metrics AS s
            ON t.session_key = s.session_key
    """
    if where:
        sql += f" WHERE {where}"
    sql += " GROUP BY s.subject_id ORDER BY s.subject_id"
    return conn.execute(sql).pl()


def sql_list_sessions(
    conn: CatalogConnection,
    *,
    subject_id: str | None = None,
    where: str | None = None,
) -> pl.DataFrame:
    """Return session rows for a subject, with trial counts and OSIM status."""

    clauses: list[str] = []
    if where:
        clauses.append(f"({where})")
    if subject_id:
        safe_subject = subject_id.replace("'", "''")
        clauses.append(f"s.subject_id = '{safe_subject}'")
    sql = """
        SELECT
            s.subject_id,
            s.session_id,
            count(*) AS n_trials,
            count(*) FILTER (WHERE t.qualifies_for_id) AS n_id_trials,
            bool_or(s.qualifies_for_osim) AS qualifies_for_osim
        FROM movedb_catalog.trial_selection_metrics AS t
        JOIN movedb_catalog.session_selection_metrics AS s
            ON t.session_key = s.session_key
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " GROUP BY s.subject_id, s.session_id ORDER BY s.subject_id, s.session_id"
    return conn.execute(sql).pl()


def sql_list_trials(
    conn: CatalogConnection,
    *,
    subject_id: str | None = None,
    session_id: str | None = None,
    where: str | None = None,
) -> pl.DataFrame:
    """Return trial rows for the current subject/session filter."""

    clauses: list[str] = []
    if where:
        clauses.append(f"({where})")
    if subject_id:
        safe_subject = subject_id.replace("'", "''")
        clauses.append(f"s.subject_id = '{safe_subject}'")
    if session_id:
        safe_session = session_id.replace("'", "''")
        clauses.append(f"s.session_id = '{safe_session}'")
    sql = """
        SELECT
            t.trial_key,
            s.subject_id,
            s.session_id,
            t.trial_name,
            t.qualifies_for_ik,
            t.qualifies_for_id,
            t.reason,
            t.t_start,
            t.t_end,
            t.fp_mapping_json
        FROM movedb_catalog.trial_selection_metrics AS t
        JOIN movedb_catalog.session_selection_metrics AS s
            ON t.session_key = s.session_key
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY s.subject_id, s.session_id, t.trial_name"
    return conn.execute(sql).pl()


def register_scratch_views(
    conn: CatalogConnection,
    *,
    session_key: str,
    trial_key: str | None,
    scratch_dir: Path,
    opensim_dir: Path,
    trial_name: str | None = None,
    replace: bool = True,
) -> dict[str, str]:
    """Register scratch outputs as temporary DuckDB views.

    The helper creates a lightweight run-log temp view in all cases and creates
    `current_ik` / `current_id` when matching scratch Parquet outputs exist.
    """

    view_prefix = "current"
    create = "CREATE OR REPLACE" if replace else "CREATE"
    registered: dict[str, str] = {}

    if trial_name is not None:
        ik_path = opensim_dir / f"{trial_name}_ik.parquet"
        id_path = opensim_dir / f"{trial_name}_id.parquet"
        if ik_path.exists():
            conn.execute(
                f"{create} TEMP VIEW {view_prefix}_ik AS SELECT * FROM read_parquet(?)",
                [str(ik_path)],
            )
            registered["ik"] = f"{view_prefix}_ik"
        if id_path.exists():
            conn.execute(
                f"{create} TEMP VIEW {view_prefix}_id AS SELECT * FROM read_parquet(?)",
                [str(id_path)],
            )
            registered["id"] = f"{view_prefix}_id"

    run_log = pl.DataFrame(
        [
            {
                "session_key": session_key,
                "trial_key": trial_key,
                "scratch_dir": str(scratch_dir),
                "opensim_dir": str(opensim_dir),
            }
        ]
    )
    conn.register("scratch_run_log_df", run_log.to_arrow())
    conn.execute(f"{create} TEMP VIEW {view_prefix}_run_log AS SELECT * FROM scratch_run_log_df")
    registered["run_log"] = f"{view_prefix}_run_log"
    return registered


def sql_compare_canonical_vs_scratch(
    conn: CatalogConnection,
    *,
    trial_key: str,
) -> pl.DataFrame:
    """Compare one canonical trial row against scratch output availability."""

    safe_trial_key = trial_key.replace("'", "''")
    sql = f"""
        WITH canonical AS (
            SELECT
                trial_key,
                qualifies_for_ik,
                qualifies_for_id,
                t_start,
                t_end
            FROM movedb_catalog.trial_selection_metrics
            WHERE trial_key = '{safe_trial_key}'
        ),
        scratch AS (
            SELECT
                (SELECT count(*) FROM information_schema.tables WHERE table_name = 'current_ik') > 0 AS has_scratch_ik,
                (SELECT count(*) FROM information_schema.tables WHERE table_name = 'current_id') > 0 AS has_scratch_id
        )
        SELECT *
        FROM canonical, scratch
    """
    return conn.execute(sql).pl()


def sql_current_view_preview(
    conn: CatalogConnection,
    *,
    view_name: str,
    limit: int = 25,
) -> pl.DataFrame:
    """Preview rows from a temporary or persistent DuckDB view."""

    safe_view_name = view_name.replace('"', '""')
    return conn.execute(f'SELECT * FROM "{safe_view_name}" LIMIT {int(limit)}').pl()
