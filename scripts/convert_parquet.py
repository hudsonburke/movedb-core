#!/usr/bin/env python3
"""Convert C3D files to Parquet catalog using movedb-core.

Thin orchestrator — all C3D parsing, data modeling, and DataFrame conversion
is done by movedb-core's adapters.

Requires: movedb-core (pip install -e ../movedb-core)

Usage::

    python scripts/convert_parquet.py --c3d-dir sourcedata/ --output data/processed/ -j 8
"""

import argparse
import logging
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def discover_c3d_files(root: str) -> list[str]:
    """Recursively find all .c3d files under root."""
    return sorted(str(p) for p in Path(root).rglob("*.c3d"))


def extract_subject(filepath: str) -> str:
    """Extract subject name from directory structure."""
    p = Path(filepath)
    if len(p.parts) >= 3:
        return p.parts[-3]
    return p.stem


def extract_session(filepath: str) -> str:
    """Extract session name from directory structure."""
    p = Path(filepath)
    if len(p.parts) >= 2:
        return p.parts[-2]
    return "unknown"


def process_subject(
    subject: str,
    trials: list[str],
    output_dir: Path,
) -> tuple[str, bool, str]:
    """Process a single subject into Parquet files using movedb-core."""
    try:
        from movedb.adapters.c3d import extract_markers, extract_forceplates, extract_events
        from movedb.adapters.polars import markers_to_polars, forceplates_to_polars, events_to_polars
        import ezc3d

        subject_dir = output_dir / subject
        subject_dir.mkdir(parents=True, exist_ok=True)

        all_markers = []
        all_forceplates = []
        all_events = []

        for trial_path in trials:
            trial_name = Path(trial_path).stem
            session = extract_session(trial_path)

            try:
                c3d = ezc3d.c3d(trial_path)

                # Extract + convert using movedb-core
                marker_data = extract_markers(c3d)
                markers_df = markers_to_polars(marker_data, trial_name=trial_name)
                markers_df = markers_df.with_columns([
                    pl.lit(subject).alias("subject_id"),
                    pl.lit(session).alias("session_id"),
                ])
                all_markers.append(markers_df)

                fp_data = extract_forceplates(c3d)
                fp_df = forceplates_to_polars(fp_data, trial_name=trial_name)
                fp_df = fp_df.with_columns([
                    pl.lit(subject).alias("subject_id"),
                    pl.lit(session).alias("session_id"),
                ])
                all_forceplates.append(fp_df)

                events = extract_events(c3d)
                events_df = events_to_polars(events, trial_name=trial_name)
                events_df = events_df.with_columns([
                    pl.lit(subject).alias("subject_id"),
                    pl.lit(session).alias("session_id"),
                ])
                if not events_df.is_empty():
                    all_events.append(events_df)

            except Exception as e:
                logger.warning(f"  Failed to process {trial_path}: {e}")
                continue

        # Write Parquet
        if all_markers:
            df = pl.concat(all_markers)
            df.write_parquet(subject_dir / "markers.parquet")
            logger.info(f"  {subject}: {len(df)} marker rows")

        if all_forceplates:
            df = pl.concat(all_forceplates)
            df.write_parquet(subject_dir / "forceplates.parquet")
            logger.info(f"  {subject}: {len(df)} forceplate rows")

        if all_events:
            df = pl.concat(all_events)
            df.write_parquet(subject_dir / "events.parquet")
            logger.info(f"  {subject}: {len(df)} events")

        return subject, True, f"{len(trials)} trials"

    except Exception as e:
        return subject, False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Convert C3D files to Parquet catalog")
    parser.add_argument("--c3d-dir", required=True, help="C3D source directory")
    parser.add_argument("--output", "-o", default="data/processed", help="Output directory")
    parser.add_argument("--workers", "-j", type=int, default=1, help="Parallel workers")
    args = parser.parse_args()

    c3d_dir = Path(args.c3d_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    c3d_files = discover_c3d_files(str(c3d_dir))
    if not c3d_files:
        logger.error(f"No C3D files found in {c3d_dir}")
        return

    logger.info(f"Found {len(c3d_files)} C3D files")

    subject_trials = defaultdict(list)
    for filepath in c3d_files:
        subject_trials[extract_subject(filepath)].append(filepath)

    logger.info(f"Grouped into {len(subject_trials)} subjects")

    results = []
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(process_subject, subject, trials, output_dir): subject
                for subject, trials in subject_trials.items()
            }
            for future in as_completed(futures):
                subject, success, msg = future.result()
                results.append((subject, success, msg))
                status = "✓" if success else "✗"
                logger.info(f"  {status} {subject}: {msg}")
    else:
        for subject, trials in subject_trials.items():
            subject, success, msg = process_subject(subject, trials, output_dir)
            results.append((subject, success, msg))
            status = "✓" if success else "✗"
            logger.info(f"  {status} {subject}: {msg}")

    success_count = sum(1 for _, success, _ in results if success)
    logger.info(f"\nDone: {success_count}/{len(results)} subjects processed")


if __name__ == "__main__":
    main()
