"""Build DuckDB catalog from Parquet files."""

from __future__ import annotations

import logging
from pathlib import Path

from .duckdb import connect_catalog
from .registry import register_session_bundle
from .views import create_catalog_views

logger = logging.getLogger(__name__)


def build_catalog(data_dir: str | Path, output_path: str | Path) -> None:
    """Build DuckDB catalog from Parquet files.

    Parameters
    ----------
    data_dir : str | Path
        Directory containing subject subdirectories with Parquet files.
    output_path : str | Path
        Output path for the DuckDB catalog database.
    """
    data_dir = Path(data_dir)
    output_path = Path(output_path)

    conn = connect_catalog(str(output_path))
    logger.info(f"Created catalog at {output_path}")

    subject_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
    logger.info(f"Found {len(subject_dirs)} subject directories")

    for subject_dir in subject_dirs:
        if not (subject_dir / "markers.parquet").exists():
            logger.warning(f"Skipping {subject_dir.name}: no markers.parquet")
            continue

        try:
            register_session_bundle(conn, subject_dir)
            logger.info(f"  Registered {subject_dir.name}")
        except Exception as e:
            logger.error(f"  Failed to register {subject_dir.name}: {e}")

    create_catalog_views(conn)

    n_sessions = conn.execute("SELECT COUNT(*) FROM movedb_catalog.sessions").fetchone()[0]
    n_trials = conn.execute("SELECT COUNT(*) FROM movedb_catalog.trials").fetchone()[0]
    logger.info(f"Catalog built: {n_sessions} sessions, {n_trials} trials")
