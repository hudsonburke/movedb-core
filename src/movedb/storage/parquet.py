"""Typed Parquet read, write, and scan helpers for movedb storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import polars as pl

from ..core import (
    AnalogMeta,
    ForceplateMeta,
    GRFMeta,
    KinematicsMeta,
    MarkerMeta,
)
from .metadata import (
    StorageMetadata,
    encode_storage_metadata,
    parse_signal_metadata,
    read_storage_metadata,
)
from .schemas import (
    AnalogLongRow,
    EventRow,
    ForceplateLongRow,
    MarkerLongRow,
    validate_df,
)
from .validation import (
    validate_analogs_wide,
    validate_forceplates_wide,
    validate_markers_wide,
)


Format = Literal["wide", "long"]


def write_markers_parquet(
    df: pl.DataFrame,
    path: Path | str,
    *,
    format: Format,
    metadata: MarkerMeta,
    require_identity: bool = False,
) -> Path:
    validated = (
        validate_df(df, MarkerLongRow)
        if format == "long"
        else validate_markers_wide(df, metadata, require_identity=require_identity)
    )
    storage_metadata = StorageMetadata(
        schema_name="markers",
        format=format,
        signal_type="markers",
        metadata=metadata.model_dump(mode="json"),
    )
    return _write_parquet(validated, path, storage_metadata)


def write_analogs_parquet(
    df: pl.DataFrame,
    path: Path | str,
    *,
    format: Format,
    metadata: AnalogMeta,
    require_identity: bool = False,
) -> Path:
    validated = (
        validate_df(df, AnalogLongRow)
        if format == "long"
        else validate_analogs_wide(df, metadata, require_identity=require_identity)
    )
    storage_metadata = StorageMetadata(
        schema_name="analogs",
        format=format,
        signal_type="analogs",
        metadata=metadata.model_dump(mode="json"),
    )
    return _write_parquet(validated, path, storage_metadata)


def write_forceplates_parquet(
    df: pl.DataFrame,
    path: Path | str,
    *,
    format: Format,
    metadata: ForceplateMeta,
    require_identity: bool = False,
) -> Path:
    validated = (
        validate_df(df, ForceplateLongRow)
        if format == "long"
        else validate_forceplates_wide(df, metadata, require_identity=require_identity)
    )
    storage_metadata = StorageMetadata(
        schema_name="forceplates",
        format=format,
        signal_type="forceplates",
        metadata=metadata.model_dump(mode="json"),
    )
    return _write_parquet(validated, path, storage_metadata)


def write_events_parquet(
    df: pl.DataFrame,
    path: Path | str,
    *,
    schema_name: str = "events",
) -> Path:
    validated = validate_df(df, EventRow)
    storage_metadata = StorageMetadata(schema_name=schema_name, format="long")
    return _write_parquet(validated, path, storage_metadata)


def read_markers_parquet(path: Path | str) -> tuple[pl.DataFrame, MarkerMeta | None, StorageMetadata | None]:
    return _read_signal_parquet(path, schema_name="markers")


def read_analogs_parquet(path: Path | str) -> tuple[pl.DataFrame, AnalogMeta | None, StorageMetadata | None]:
    return _read_signal_parquet(path, schema_name="analogs")


def read_forceplates_parquet(path: Path | str) -> tuple[pl.DataFrame, ForceplateMeta | None, StorageMetadata | None]:
    return _read_signal_parquet(path, schema_name="forceplates")


def read_events_parquet(path: Path | str) -> tuple[pl.DataFrame, StorageMetadata | None]:
    df = pl.read_parquet(path)
    return validate_df(df, EventRow), read_storage_metadata(path)


def scan_markers_parquet(path: Path | str) -> pl.LazyFrame:
    return _scan_and_validate(path, MarkerLongRow)


def scan_analogs_parquet(path: Path | str) -> pl.LazyFrame:
    return _scan_and_validate(path, AnalogLongRow)


def scan_forceplates_parquet(path: Path | str) -> pl.LazyFrame:
    return _scan_and_validate(path, ForceplateLongRow)


def scan_events_parquet(path: Path | str) -> pl.LazyFrame:
    return _scan_base_validated(path)


def write_parquet(df: pl.DataFrame, path: Path | str, metadata: dict[str, Any] | None = None) -> Path:
    storage_metadata = None
    if metadata is not None:
        storage_metadata = StorageMetadata(
            schema_name=str(metadata.get("type", "table")),
            format="wide",
            signal_type=metadata.get("type"),
            metadata=metadata,
        )
    return _write_parquet(df, path, storage_metadata)


def read_parquet(path: Path | str) -> tuple[pl.DataFrame, dict[str, Any] | None]:
    df = pl.read_parquet(path)
    metadata = read_storage_metadata(path)
    return df, (metadata.metadata if metadata is not None else None)


def scan_parquet(path: Path | str) -> pl.LazyFrame:
    return pl.scan_parquet(path)


# --- Kinematics Parquet I/O -------------------------------------------------


def write_kinematics_parquet(
    df: pl.DataFrame,
    path: Path | str,
    *,
    format: Format,
    metadata: KinematicsMeta,
) -> Path:
    """Write a kinematics DataFrame to Parquet with embedded metadata."""
    validated = _assert_base_columns(df, format)
    storage_metadata = StorageMetadata(
        schema_name="kinematics",
        format=format,
        signal_type="kinematics",
        metadata=metadata.model_dump(mode="json"),
    )
    return _write_parquet(validated, path, storage_metadata)


def read_kinematics_parquet(
    path: Path | str,
) -> tuple[pl.DataFrame, KinematicsMeta | None, StorageMetadata | None]:
    """Read a kinematics Parquet file, returning (df, metadata, storage_metadata)."""
    return _read_signal_parquet(path, schema_name="kinematics")


def scan_kinematics_parquet(path: Path | str) -> pl.LazyFrame:
    """Lazily scan a kinematics Parquet file."""
    return _scan_base_validated(path)


# --- GRF Parquet I/O --------------------------------------------------------


def write_grf_parquet(
    df: pl.DataFrame,
    path: Path | str,
    *,
    format: Format,
    metadata: GRFMeta,
) -> Path:
    """Write a GRF DataFrame to Parquet with embedded metadata."""
    validated = _assert_base_columns(df, format)
    storage_metadata = StorageMetadata(
        schema_name="grf",
        format=format,
        signal_type="grf",
        metadata=metadata.model_dump(mode="json"),
    )
    return _write_parquet(validated, path, storage_metadata)


def read_grf_parquet(
    path: Path | str,
) -> tuple[pl.DataFrame, GRFMeta | None, StorageMetadata | None]:
    """Read a GRF Parquet file, returning (df, metadata, storage_metadata)."""
    return _read_signal_parquet(path, schema_name="grf")


def scan_grf_parquet(path: Path | str) -> pl.LazyFrame:
    """Lazily scan a GRF Parquet file."""
    return _scan_base_validated(path)


# --- Internal helpers -------------------------------------------------------


def _assert_base_columns(df: pl.DataFrame, format: Format) -> pl.DataFrame:
    """Validate base columns present in all signal DataFrames, return df."""
    required = {"time", "frame"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in {format}-format DataFrame: {missing}"
        )
    return df



def _read_signal_parquet(path: Path | str, *, schema_name: str) -> tuple[pl.DataFrame, Any | None, StorageMetadata | None]:
    df = pl.read_parquet(path)
    storage_metadata = read_storage_metadata(path)
    signal_meta = parse_signal_metadata(storage_metadata)
    df = _drop_optional_identity_columns(df)
    fmt = storage_metadata.format if storage_metadata else "wide"

    if schema_name in ("markers", "analogs", "forceplates"):
        _LONG_MODELS = {"markers": MarkerLongRow, "analogs": AnalogLongRow, "forceplates": ForceplateLongRow}
        _WIDE_VALIDATORS = {"markers": validate_markers_wide, "analogs": validate_analogs_wide, "forceplates": validate_forceplates_wide}
        if storage_metadata is not None and fmt == "long":
            df = validate_df(df, _LONG_MODELS[schema_name])
        elif signal_meta is not None:
            df = _WIDE_VALIDATORS[schema_name](df, signal_meta)
    # kinematics / grf: base-column check only (signal columns vary)
    elif schema_name in ("kinematics", "grf") and storage_metadata is not None:
        _assert_base_columns(df, fmt)

    return df, signal_meta, storage_metadata


def _write_parquet(df: pl.DataFrame, path: Path | str, metadata: StorageMetadata | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path, metadata=encode_storage_metadata(metadata))
    return path


def _scan_base_validated(path: Path | str) -> pl.LazyFrame:
    """Lazily scan and validate that base columns (time, frame) are present."""
    lazy = pl.scan_parquet(path)
    schema = lazy.collect_schema()
    missing = [c for c in ("time", "frame") if c not in schema]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    return lazy


def _scan_and_validate(path: Path | str, model: type[MarkerLongRow | AnalogLongRow | ForceplateLongRow | EventRow]) -> pl.LazyFrame:
    lazy = pl.scan_parquet(path)
    storage_metadata = read_storage_metadata(path)
    if storage_metadata is not None and storage_metadata.format == "long":
        schema_before = lazy.collect_schema()
        drop_columns = [name for name in ("subject_id", "session_id") if name in schema_before]
        if drop_columns:
            lazy = lazy.drop(drop_columns)
    schema = lazy.collect_schema()
    missing = [column for column in model.columns if column not in schema]
    missing_required = [column for column in missing if column not in model.nullable_columns]
    if missing_required:
        raise ValueError(f"Missing required columns for {model.__name__}: {', '.join(missing)}.")
    return lazy


def _drop_optional_identity_columns(df: pl.DataFrame) -> pl.DataFrame:
    optional = [name for name in ("subject_id", "session_id") if name in df.columns and df[name].null_count() == df.height]
    if not optional:
        return df
    return df.drop(optional)
