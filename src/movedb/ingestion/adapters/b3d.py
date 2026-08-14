"""Batch ingestion of b3d datasets into per-subject Parquet bundles.

This module provides a high-level ``ingest_b3d_dataset()`` function that
discovers ``*.b3d`` files, extracts all signal types using the existing
``movedb.adapters.nimble`` extractors, converts them to long-format Polars
DataFrames via ``movedb.adapters.polars``, and writes one Parquet file per
subject per signal type.

DuckDB ``read_parquet('data/kinematics/*.parquet')`` glob patterns unify the
per-subject files for dataset-level querying.

Requires ``nimblephysics`` (install with ``pip install movedb-core[b3d]``).

Example::

    from movedb.adapters.b3d_ingest import ingest_b3d_dataset

    stats = ingest_b3d_dataset(
        data_roots=[Path("Downloads/test"), Path("Downloads/train")],
        output_dir=Path("data"),
        workers=8,
    )
    print(stats)
"""
from __future__ import annotations

import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

try:
    import nimblephysics as nimble
except ImportError:
    nimble = None  # type: ignore[assignment]

from .nimble import (
    extract_subject_metadata,
    extract_kinematics,
    extract_grf,
    extract_markers as extract_b3d_markers,
    extract_forceplates as extract_b3d_forceplates,
)
from .polars import (
    kinematics_to_polars,
    grf_to_polars,
    markers_to_polars,
    forceplates_to_polars,
)


# ---------------------------------------------------------------------------
# Path metadata
# ---------------------------------------------------------------------------

@dataclass
class B3DFileDescriptor:
    """Resolved metadata for a single b3d file."""
    path: Path
    data_root: Path
    dataset_split: str
    model_type: str
    study: str
    subject_dir: str
    subject_id: str


def resolve_b3d_path(b3d_path: Path, data_root: Path) -> B3DFileDescriptor:
    """Extract dataset metadata from a b3d file's path.

    Expects the layout::

        {data_root}/[{split}/]{model_type}/{study}/{subject_dir}/file.b3d

    If ``data_root`` itself is ``test/`` or ``train/``, the split is inferred
    from ``data_root.name``; otherwise it is taken from the first path
    component.
    """
    rel = b3d_path.relative_to(data_root)
    parts = rel.parts

    if len(parts) >= 2 and parts[0] in ("test", "train"):
        dataset_split = parts[0]
        offset = 1
    else:
        dataset_split = data_root.name
        offset = 0

    model_type = parts[offset] if len(parts) > offset else "unknown"
    study = parts[offset + 1] if len(parts) > offset + 1 else "unknown"
    subject_dir = parts[offset + 2] if len(parts) > offset + 2 else b3d_path.stem
    subject_id = f"{study}__{subject_dir}"

    return B3DFileDescriptor(
        path=b3d_path,
        data_root=data_root,
        dataset_split=dataset_split,
        model_type=model_type,
        study=study,
        subject_dir=subject_dir,
        subject_id=subject_id,
    )


def discover_b3d_files(data_roots: list[Path]) -> list[B3DFileDescriptor]:
    """Find all ``*.b3d`` files under the given roots, skipping hidden dirs."""
    results: list[B3DFileDescriptor] = []
    for root in data_roots:
        for p in sorted(root.rglob("*.b3d")):
            rel = p.relative_to(root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            results.append(resolve_b3d_path(p, root))
    return results


# ---------------------------------------------------------------------------
# Subject metadata extraction
# ---------------------------------------------------------------------------

def extract_subject_row(descriptor: B3DFileDescriptor) -> dict[str, Any]:
    """Extract one metadata row for a subject."""
    if nimble is None:
        raise ImportError("nimblephysics is required for b3d ingestion")
    subject = nimble.biomechanics.SubjectOnDisk(str(descriptor.path))
    meta = extract_subject_metadata(subject)

    return {
        "subject_id": descriptor.subject_id,
        "source_file": str(descriptor.path),
        "dataset_split": descriptor.dataset_split,
        "model_type": descriptor.model_type,
        "study": descriptor.study,
        "subject_dir": descriptor.subject_dir,
        "mass_kg": meta.mass_kg,
        "height_m": meta.height_m,
        "age_years": meta.age_years,
        "biological_sex": meta.biological_sex,
        "num_dofs": meta.num_dofs,
        "dof_names": meta.dof_names,
        "body_names": meta.body_names,
        "ground_force_bodies": meta.ground_force_bodies,
        "num_trials": meta.num_trials,
        "num_processing_passes": meta.num_processing_passes,
        "quality": meta.quality,
        "tags": meta.subject_tags,
        "href": meta.href,
    }


def extract_trial_rows(descriptor: B3DFileDescriptor) -> pl.DataFrame:
    """Extract one metadata row per trial for a subject."""
    if nimble is None:
        raise ImportError("nimblephysics is required for b3d ingestion")
    subject = nimble.biomechanics.SubjectOnDisk(str(descriptor.path))
    meta = extract_subject_metadata(subject)

    rows = []
    for t in range(meta.num_trials):
        rows.append({
            "subject_id": descriptor.subject_id,
            "trial_name": meta.trial_names[t],
            "trial_index": t,
            "num_frames": meta.trial_lengths[t],
            "timestep": round(meta.trial_timesteps[t], 8),
            "duration_s": round(meta.trial_lengths[t] * meta.trial_timesteps[t], 4),
        })
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# Timeseries extraction
# ---------------------------------------------------------------------------

def extract_subject_kinematics(descriptor: B3DFileDescriptor) -> pl.DataFrame:
    """Extract all trials' kinematics as a long-format DataFrame."""
    if nimble is None:
        raise ImportError("nimblephysics is required for b3d ingestion")
    subject = nimble.biomechanics.SubjectOnDisk(str(descriptor.path))
    pass_idx = subject.getNumProcessingPasses() - 1
    frames: list[pl.DataFrame] = []

    for t in range(subject.getNumTrials()):
        try:
            kin = extract_kinematics(subject, t, processing_pass=pass_idx)
            df = kinematics_to_polars(kin, format="long", trial_name=subject.getTrialName(t))
            df = df.insert_column(0, pl.Series("subject_id", [descriptor.subject_id] * df.height))
            frames.append(df)
        except Exception:
            continue

    return pl.concat(frames) if frames else pl.DataFrame()


def extract_subject_markers(descriptor: B3DFileDescriptor) -> pl.DataFrame:
    """Extract all trials' markers as a long-format DataFrame (sparse)."""
    if nimble is None:
        raise ImportError("nimblephysics is required for b3d ingestion")
    subject = nimble.biomechanics.SubjectOnDisk(str(descriptor.path))
    frames: list[pl.DataFrame] = []

    for t in range(subject.getNumTrials()):
        try:
            mkr = extract_b3d_markers(subject, t)
            df = markers_to_polars(mkr, format="long", trial_name=subject.getTrialName(t))
            df = df.insert_column(0, pl.Series("subject_id", [descriptor.subject_id] * df.height))
            frames.append(df)
        except Exception:
            continue

    return pl.concat(frames) if frames else pl.DataFrame()


def extract_subject_grf(descriptor: B3DFileDescriptor) -> pl.DataFrame:
    """Extract all trials' GRF as a long-format DataFrame."""
    if nimble is None:
        raise ImportError("nimblephysics is required for b3d ingestion")
    subject = nimble.biomechanics.SubjectOnDisk(str(descriptor.path))
    pass_idx = subject.getNumProcessingPasses() - 1
    frames: list[pl.DataFrame] = []

    for t in range(subject.getNumTrials()):
        try:
            grf = extract_grf(subject, t, processing_pass=pass_idx)
            df = grf_to_polars(grf, format="long", trial_name=subject.getTrialName(t))
            df = df.insert_column(0, pl.Series("subject_id", [descriptor.subject_id] * df.height))
            frames.append(df)
        except Exception:
            continue

    return pl.concat(frames) if frames else pl.DataFrame()


def extract_subject_forceplates(descriptor: B3DFileDescriptor) -> pl.DataFrame:
    """Extract all trials' force plate data as a long-format DataFrame."""
    if nimble is None:
        raise ImportError("nimblephysics is required for b3d ingestion")
    subject = nimble.biomechanics.SubjectOnDisk(str(descriptor.path))
    frames: list[pl.DataFrame] = []

    for t in range(subject.getNumTrials()):
        try:
            fp = extract_b3d_forceplates(subject, t)
            if fp is None:
                continue
            df = forceplates_to_polars(fp, format="long", trial_name=subject.getTrialName(t))
            df = df.insert_column(0, pl.Series("subject_id", [descriptor.subject_id] * df.height))
            frames.append(df)
        except Exception:
            continue

    return pl.concat(frames) if frames else pl.DataFrame()


# ---------------------------------------------------------------------------
# Single-subject processing (used by both serial and parallel paths)
# ---------------------------------------------------------------------------

SIGNAL_EXTRACTORS = {
    "kinematics": extract_subject_kinematics,
    "markers": extract_subject_markers,
    "grf": extract_subject_grf,
    "forceplates": extract_subject_forceplates,
}


@dataclass
class SubjectResult:
    """Outcome of processing a single subject."""
    subject_id: str
    success: bool
    signal_row_counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None


def _process_one_subject(
    descriptor: B3DFileDescriptor,
    output_dir: Path,
    active_signals: set[str],
    compression: str,
) -> SubjectResult:
    """Extract all data for one subject and write Parquet files.

    This is a top-level function (not a closure) so it can be pickled
    for multiprocessing.
    """
    sid = descriptor.subject_id
    try:
        # Subject metadata
        sub_row = extract_subject_row(descriptor)
        pl.DataFrame([sub_row]).write_parquet(
            output_dir / "subjects" / f"{sid}.parquet",
            compression=compression,
        )

        # Trial metadata
        trial_df = extract_trial_rows(descriptor)
        trial_df.write_parquet(
            output_dir / "trials" / f"{sid}.parquet",
            compression=compression,
        )

        # Signal timeseries
        row_counts: dict[str, int] = {}
        for sig in active_signals:
            extractor = SIGNAL_EXTRACTORS[sig]
            df = extractor(descriptor)
            n = df.height
            if n > 0:
                df.write_parquet(
                    output_dir / sig / f"{sid}.parquet",
                    compression=compression,
                )
            row_counts[sig] = n

        return SubjectResult(subject_id=sid, success=True, signal_row_counts=row_counts)

    except Exception as exc:
        return SubjectResult(subject_id=sid, success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Dataset-level ingestion
# ---------------------------------------------------------------------------

@dataclass
class IngestStats:
    """Result summary from ``ingest_b3d_dataset``."""
    subjects_completed: int = 0
    subjects_failed: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    signal_row_counts: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0


def ingest_b3d_dataset(
    data_roots: list[Path],
    output_dir: Path,
    *,
    signals: list[str] | None = None,
    skip_signals: list[str] | None = None,
    compression: str = "zstd",
    workers: int = 1,
    progress: bool = True,
) -> IngestStats:
    """Ingest an AddBiomechanics dataset into per-subject Parquet bundles.

    Parameters
    ----------
    data_roots:
        Directories containing ``*.b3d`` files (recursively searched).
    output_dir:
        Root output directory. Creates ``{output_dir}/{signal}/`` subdirs.
    signals:
        Which signals to extract. Defaults to all available
        (kinematics, markers, grf, forceplates).
    skip_signals:
        Signals to skip.
    compression:
        Parquet compression codec.
    workers:
        Number of parallel worker processes.  ``1`` (default) runs
        sequentially in the current process.  Values > 1 use a
        ``ProcessPoolExecutor``.
    progress:
        Show tqdm progress bar (requires tqdm).

    Returns
    -------
    IngestStats
        Summary of what was ingested.
    """
    if nimble is None:
        raise ImportError("nimblephysics is required for b3d ingestion")

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None  # type: ignore[assignment]

    # Resolve signal set
    all_signals = set(SIGNAL_EXTRACTORS.keys())
    active_signals = all_signals if signals is None else set(signals)
    if skip_signals:
        active_signals -= set(skip_signals)

    # Create output directories
    for sig in {"subjects", "trials"} | active_signals:
        (output_dir / sig).mkdir(parents=True, exist_ok=True)

    # Discover files
    descriptors = discover_b3d_files(data_roots)
    if not descriptors:
        return IngestStats()

    # Find already-completed subjects
    completed: set[str] = set()
    for p in (output_dir / "subjects").glob("*.parquet"):
        completed.add(p.stem)

    remaining = [d for d in descriptors if d.subject_id not in completed]

    stats = IngestStats(signal_row_counts={s: 0 for s in active_signals})
    t_start = time.time()

    if workers > 1:
        _run_parallel(remaining, output_dir, active_signals, compression,
                      workers, stats, progress, tqdm)
    else:
        _run_serial(remaining, output_dir, active_signals, compression,
                    stats, progress, tqdm)

    stats.elapsed_seconds = time.time() - t_start

    # Write consolidated metadata tables
    _consolidate_metadata(output_dir, compression)

    return stats


def _run_serial(
    remaining: list[B3DFileDescriptor],
    output_dir: Path,
    active_signals: set[str],
    compression: str,
    stats: IngestStats,
    progress: bool,
    tqdm: Any,
) -> None:
    """Sequential ingestion loop."""
    iterator: Any = remaining
    if progress and tqdm is not None:
        iterator = tqdm(remaining, desc="Ingesting", unit="subject")

    for desc in iterator:
        if progress and tqdm is not None:
            iterator.set_postfix_str(desc.subject_id, refresh=False)

        result = _process_one_subject(desc, output_dir, active_signals, compression)
        _apply_result(result, stats, output_dir)


def _run_parallel(
    remaining: list[B3DFileDescriptor],
    output_dir: Path,
    active_signals: set[str],
    compression: str,
    workers: int,
    stats: IngestStats,
    progress: bool,
    tqdm: Any,
) -> None:
    """Parallel ingestion using ProcessPoolExecutor."""
    pbar = tqdm(total=len(remaining), desc="Ingesting", unit="subject") if progress and tqdm else None

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _process_one_subject, desc, output_dir, active_signals, compression
            ): desc
            for desc in remaining
        }

        for future in as_completed(futures):
            result = future.result()
            _apply_result(result, stats, output_dir)
            if pbar is not None:
                pbar.update(1)
                pbar.set_postfix_str(result.subject_id, refresh=False)

    if pbar is not None:
        pbar.close()


def _apply_result(result: SubjectResult, stats: IngestStats, output_dir: Path) -> None:
    """Update stats from a SubjectResult, write error log on failure."""
    if result.success:
        stats.subjects_completed += 1
        for sig, count in result.signal_row_counts.items():
            stats.signal_row_counts[sig] += count
    else:
        stats.subjects_failed += 1
        stats.errors.append((result.subject_id, result.error or "unknown"))
        with open(output_dir / "ingest_errors.log", "a") as f:
            f.write(f"\n{'='*60}\n{result.subject_id}\n{result.error}\n")


def _consolidate_metadata(output_dir: Path, compression: str) -> None:
    """Merge per-subject metadata files into consolidated tables."""
    # subjects
    sub_files = list((output_dir / "subjects").glob("*.parquet"))
    if sub_files:
        df = pl.concat([pl.read_parquet(f) for f in sub_files]).unique(subset=["subject_id"])
        df.write_parquet(output_dir / "subjects.parquet", compression=compression)

    # trials
    trial_files = list((output_dir / "trials").glob("*.parquet"))
    if trial_files:
        df = pl.concat([pl.read_parquet(f) for f in trial_files]).unique()
        df.write_parquet(output_dir / "trials.parquet", compression=compression)
