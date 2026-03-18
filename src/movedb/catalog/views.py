"""Reusable DuckDB view creation helpers."""

from __future__ import annotations

from pathlib import Path

import duckdb

from .sql import TRIALS_VIEW_SQL


def create_bundle_views(conn: duckdb.DuckDBPyConnection, session_dir: str | Path) -> None:
    """Expose canonical bundle files as local DuckDB views."""

    session_dir = Path(session_dir)
    view_files = {
        "markers_wide": session_dir / "markers.parquet",
        "analogs_wide": session_dir / "analogs.parquet",
        "forceplates_wide": session_dir / "forceplates.parquet",
        "events": session_dir / "events.parquet",
        "session_parameters": session_dir / "parameters.parquet",
    }
    for view_name, path in view_files.items():
        if path.exists():
            quoted_path = str(path).replace("'", "''")
            conn.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{quoted_path}')"
            )


def create_catalog_views(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the first global catalog views over registered bundles."""

    if _has_file_kind(conn, "parameters"):
        _create_union_view(conn, "session_parameters", file_kind="parameters")
    if _has_file_kind(conn, "events"):
        _create_union_view(conn, "events", file_kind="events")
        conn.execute(TRIALS_VIEW_SQL)


def _has_file_kind(conn: duckdb.DuckDBPyConnection, file_kind: str) -> bool:
    result = conn.execute(
        "SELECT COUNT(*) FROM movedb_catalog.session_files WHERE file_kind = ?",
        [file_kind],
    ).fetchone()
    return bool(result and result[0])


def _create_union_view(
    conn: duckdb.DuckDBPyConnection,
    view_name: str,
    *,
    file_kind: str,
) -> None:
    paths = conn.execute(
        "SELECT path FROM movedb_catalog.session_files WHERE file_kind = ? ORDER BY path",
        [file_kind],
    ).fetchall()
    if not paths:
        return
    unions = [
        f"SELECT * FROM read_parquet('{path[0].replace(chr(39), chr(39) * 2)}')"
        for path in paths
    ]
    sql = f"CREATE OR REPLACE VIEW movedb_catalog.{view_name} AS " + " UNION ALL ".join(unions)
    conn.execute(sql)
