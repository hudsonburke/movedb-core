"""Create a DuckDB catalog for the AddBiomechanics demo dataset.

Registers views over the per-subject Parquet bundles produced by
``b3d_ingest.ingest_b3d_dataset()`` so queries can use stable view
names instead of glob patterns.

Usage::

    from movedb.adapters.b3d_catalog import create_b3d_catalog
    conn = create_b3d_catalog(Path("data"), Path("catalog.duckdb"))

Then in queries::

    SELECT * FROM subjects WHERE study = 'Carter2023_Formatted_With_Arm'
    SELECT * FROM kinematics WHERE dof_name = 'knee_angle_l' LIMIT 10
"""
from __future__ import annotations

from pathlib import Path

import duckdb


def create_b3d_catalog(
    data_dir: Path,
    catalog_path: Path | None = None,
    *,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Create or open a DuckDB catalog with views over b3d Parquet bundles.

    Parameters
    ----------
    data_dir:
        Root directory containing ``subjects.parquet``, ``trials.parquet``,
        and per-signal subdirectories (``kinematics/``, ``markers/``, etc.).
    catalog_path:
        Path to the DuckDB database file.  If ``None``, uses an in-memory
        database.
    read_only:
        Open the catalog in read-only mode.

    Returns
    -------
    duckdb.DuckDBPyConnection
        A DuckDB connection with the following views available:
        ``subjects``, ``trials``, ``kinematics``, ``markers``, ``grf``,
        ``forceplates``.
    """
    database = str(catalog_path) if catalog_path else ":memory:"
    conn = duckdb.connect(database=database, read_only=read_only)

    data_dir = data_dir.resolve()

    # Metadata tables (single Parquet files)
    for name in ("subjects", "trials"):
        path = data_dir / f"{name}.parquet"
        if path.exists():
            conn.execute(f"""
                CREATE OR REPLACE VIEW {name} AS
                SELECT * FROM read_parquet('{path}')
            """)

    # Signal views (glob over per-subject files)
    for name in ("kinematics", "markers", "grf", "forceplates"):
        subdir = data_dir / name
        if subdir.is_dir() and any(subdir.glob("*.parquet")):
            glob_path = str(subdir / "*.parquet")
            conn.execute(f"""
                CREATE OR REPLACE VIEW {name} AS
                SELECT * FROM read_parquet('{glob_path}')
            """)

    # Convenience: dataset overview
    conn.execute("""
        CREATE OR REPLACE VIEW dataset_summary AS
        SELECT
            s.study,
            s.model_type,
            s.dataset_split,
            COUNT(DISTINCT s.subject_id) AS n_subjects,
            SUM(s.num_trials) AS n_trials,
            SUM(s.num_dofs) AS total_dofs
        FROM subjects s
        GROUP BY s.study, s.model_type, s.dataset_split
        ORDER BY s.study, s.dataset_split
    """)

    return conn
