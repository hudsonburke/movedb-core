#!/usr/bin/env python3
"""Build DuckDB catalog from Parquet files using movedb-core.

Usage::

    python scripts/build_catalog.py --data-dir data/processed/ --output catalog.db
"""

import argparse
import logging
from pathlib import Path

import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_catalog(data_dir: Path, output_path: Path) -> None:
    """Build DuckDB catalog from Parquet files."""
    try:
        from movedb.catalog import connect_catalog, register_session_bundle
    except ImportError:
        logger.error("movedb-core not installed. Run: pip install -e '.[all]'")
        return

    # Connect to catalog
    conn = connect_catalog(str(output_path))
    logger.info(f"Created catalog at {output_path}")

    # Discover subject directories
    subject_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
    logger.info(f"Found {len(subject_dirs)} subject directories")

    # Register each subject as a session bundle
    for subject_dir in subject_dirs:
        subject_id = subject_dir.name

        # Check for required files
        markers_path = subject_dir / "markers.parquet"
        if not markers_path.exists():
            logger.warning(f"Skipping {subject_id}: no markers.parquet")
            continue

        try:
            # Register the session bundle
            register_session_bundle(conn, subject_dir)
            logger.info(f"  Registered {subject_id}")

        except Exception as e:
            logger.error(f"  Failed to register {subject_id}: {e}")

    # Create catalog views
    from movedb.catalog import create_catalog_views
    create_catalog_views(conn)

    logger.info(f"Catalog built at {output_path}")

    # Summary
    result = conn.execute("SELECT COUNT(*) FROM movedb_catalog.sessions")
    n_sessions = result.fetchone()[0]
    logger.info(f"  Sessions: {n_sessions}")

    result = conn.execute("SELECT COUNT(*) FROM movedb_catalog.trials")
    n_trials = result.fetchone()[0]
    logger.info(f"  Trials: {n_trials}")


def main():
    parser = argparse.ArgumentParser(description="Build DuckDB catalog from Parquet files")
    parser.add_argument("--data-dir", required=True, help="Directory with subject Parquet files")
    parser.add_argument("--output", "-o", default="data/processed/catalog.db", help="Output catalog path")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_path = Path(args.output)

    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return

    build_catalog(data_dir, output_path)


if __name__ == "__main__":
    main()
