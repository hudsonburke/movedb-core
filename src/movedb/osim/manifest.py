"""Manifest Parquet I/O for tracking OpenSim artifact rows."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from .types import OsimArtifactRow


def write_manifest(path: Path, artifacts: list[OsimArtifactRow]) -> None:
    """Write list of OsimArtifactRow dicts to a Parquet manifest file.
    
    Creates parent directories and overwrites any existing manifest.
    
    Args:
        path: Path where manifest Parquet file will be written.
        artifacts: List of OsimArtifactRow dictionaries to write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if not artifacts:
        df = pl.DataFrame()
    else:
        df = pl.DataFrame(artifacts)
    
    df.write_parquet(path)


def read_manifest(path: Path) -> list[OsimArtifactRow]:
    """Read manifest Parquet file and return list of OsimArtifactRow dicts.
    
    Returns empty list if file does not exist (not an error).
    Converts each row back to OsimArtifactRow with None for null values.
    
    Args:
        path: Path to manifest Parquet file.
    
    Returns:
        List of OsimArtifactRow dictionaries. Empty list if file doesn't exist.
    """
    path = Path(path)
    
    if not path.exists():
        return []
    
    df = pl.read_parquet(path)
    
    if df.height == 0:
        return []
    
    return [row_dict for row_dict in df.to_dicts()]


def append_to_manifest(path: Path, artifacts: list[OsimArtifactRow]) -> None:
    """Append artifacts to existing manifest, deduplicating by artifact_id.
    
    Reads existing manifest (may be empty), merges with new artifacts,
    deduplicates by artifact_id (latest/new entry wins), and writes combined list.
    
    This is the primary write path for pipeline scripts.
    
    Args:
        path: Path to manifest Parquet file.
        artifacts: List of OsimArtifactRow dictionaries to append.
    """
    existing = read_manifest(path)
    
    existing_by_id = {row["artifact_id"]: row for row in existing}
    for artifact in artifacts:
        existing_by_id[artifact["artifact_id"]] = artifact
    
    write_manifest(path, list(existing_by_id.values()))
