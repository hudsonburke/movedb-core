"""Reusable DuckDB view creation helpers."""

from __future__ import annotations

from pathlib import Path

from .protocols import CatalogConnection
from .sql import (
    ID_TRIALS_VIEW_SQL,
    QUALIFIED_TRIALS_VIEW_SQL,
    SESSION_SELECTION_METRICS_VIEW_SQL,
    SESSION_INVENTORY_VIEW_SQL,
    TRIAL_SELECTION_METRICS_VIEW_SQL,
    TRIALS_VIEW_SQL,
    TRIAL_MANIFEST_VIEW_SQL,
)


def create_bundle_views(conn: CatalogConnection, session_dir: str | Path) -> None:
    """Expose canonical bundle files as local DuckDB views."""

    session_dir = Path(session_dir)
    view_files = {
        "markers_wide": session_dir / "markers.parquet",
        "analogs_wide": session_dir / "analogs.parquet",
        "forceplates_wide": session_dir / "forceplates.parquet",
        "kinematics_wide": session_dir / "kinematics.parquet",
        "grf_wide": session_dir / "grf.parquet",
        "events": session_dir / "events.parquet",
        "session_parameters": session_dir / "parameters.parquet",
    }
    for view_name, path in view_files.items():
        if path.exists():
            quoted_path = str(path).replace("'", "''")
            conn.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{quoted_path}')"
            )


def create_catalog_views(conn: CatalogConnection) -> None:
    """Create the first global catalog views over registered bundles."""

    conn.execute(SESSION_INVENTORY_VIEW_SQL)
    if _create_registered_file_view(conn, "parameters", view_name="session_parameters"):
        pass
    if _create_registered_file_view(conn, "events", view_name="events"):
        conn.execute(TRIALS_VIEW_SQL)
        conn.execute(TRIAL_MANIFEST_VIEW_SQL)
    _create_registered_file_view(conn, "markers", view_name="markers")
    _create_registered_file_view(conn, "forceplates", view_name="forceplates")
    _create_registered_file_view(conn, "analogs", view_name="analogs")
    _create_registered_file_view(conn, "kinematics", view_name="kinematics")
    _create_registered_file_view(conn, "grf", view_name="grf")
    if _glob_exists(conn, "sub-*/ses-*/opensim/*_ik.parquet"):
        _create_glob_view(conn, "opensim_ik", relative_pattern="sub-*/ses-*/opensim/*_ik.parquet")
    if _glob_exists(conn, "sub-*/ses-*/opensim/*_id.parquet"):
        _create_glob_view(conn, "opensim_id", relative_pattern="sub-*/ses-*/opensim/*_id.parquet")
    conn.execute(SESSION_SELECTION_METRICS_VIEW_SQL)
    conn.execute(TRIAL_SELECTION_METRICS_VIEW_SQL)
    conn.execute(QUALIFIED_TRIALS_VIEW_SQL)
    conn.execute(ID_TRIALS_VIEW_SQL)


def _has_file_kind(conn: CatalogConnection, file_kind: str) -> bool:
    result = conn.execute(
        "SELECT COUNT(*) FROM movedb_catalog.session_files WHERE file_kind = ?",
        [file_kind],
    ).fetchone()
    return bool(result and result[0])


def _glob_exists(conn: CatalogConnection, relative_pattern: str) -> bool:
    dataset_root = _get_dataset_root(conn)
    if dataset_root is None:
        return False
    return any(dataset_root.glob(relative_pattern))


def _create_registered_file_view(conn: CatalogConnection, file_kind: str, *, view_name: str) -> bool:
    rows = conn.execute(
        "SELECT path FROM movedb_catalog.session_files WHERE file_kind = ? ORDER BY path",
        [file_kind],
    ).fetchall()
    if not rows:
        return False

    selects = []
    for (path,) in rows:
        quoted_path = str(path).replace("'", "''")
        selects.append(f"SELECT * FROM read_parquet('{quoted_path}')")

    conn.execute(f"CREATE OR REPLACE VIEW movedb_catalog.{view_name} AS {' UNION ALL '.join(selects)}")
    return True


def _create_glob_view(
    conn: CatalogConnection,
    view_name: str,
    *,
    relative_pattern: str,
) -> bool:
    dataset_root = _get_dataset_root(conn)
    if dataset_root is None:
        return False
    glob_path = str((dataset_root / relative_pattern).resolve()).replace("'", "''")
    conn.execute(
        f"CREATE OR REPLACE VIEW movedb_catalog.{view_name} AS SELECT * FROM '{glob_path}'"
    )
    return True


def _get_dataset_root(conn: CatalogConnection) -> Path | None:
    row = conn.execute(
        "SELECT setting_value FROM movedb_catalog.catalog_settings WHERE setting_key = 'dataset_root'"
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return Path(row[0])
