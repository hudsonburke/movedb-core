"""Typed JSON and Parquet helpers for session parameters."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar, cast

import polars as pl

from ..core import SessionParameters
from .metadata import StorageMetadata, encode_storage_metadata, read_storage_metadata
from .schemas import SessionParametersRow

T = TypeVar("T", bound=SessionParameters)


def parameters_to_polars(params: SessionParameters) -> pl.DataFrame:
    """Convert a typed parameter model into a single-row DataFrame."""

    return pl.DataFrame([params.to_record()])


def write_parameters_json(params: SessionParameters, path: str | Path) -> Path:
    """Write session parameters as a readable JSON sidecar."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(params.model_dump_json(indent=2))
    return path


def read_parameters_json(path: str | Path, model: type[T]) -> T:
    """Read session parameters from JSON and validate against a model."""

    payload = model.model_validate_json(Path(path).read_text())
    return payload


def write_parameters_parquet(params: SessionParameters, path: str | Path) -> Path:
    """Write session parameters as a one-row Parquet table."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = validate_parameters(parameters_to_polars(params))
    metadata = StorageMetadata(
        schema_name="session_parameters",
        format="long",
        signal_type="parameters",
        metadata={
            "parameter_schema": type(params).schema_name(),
            "parameter_schema_version": type(params).schema_version,
        },
    )
    df.write_parquet(path, metadata=encode_storage_metadata(metadata))
    return path


def read_parameters_parquet(path: str | Path, model: type[T]) -> tuple[T, StorageMetadata | None]:
    """Read typed session parameters from a one-row Parquet table."""

    df = validate_parameters(pl.read_parquet(path))
    rows = df.to_dicts()
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one parameter row in {path}, found {len(rows)}.")
    params = cast(T, model.from_payload(rows[0]))
    metadata = read_storage_metadata(path)
    return params, metadata


def read_session_parameters(session_dir: str | Path, model: type[T]) -> tuple[T, StorageMetadata | None]:
    """Read typed session parameters from a session motion directory.

    This looks for `parameters.parquet` inside the provided directory and uses
    the typed Parquet reader so callers do not need to assemble the filename.
    """

    session_dir = Path(session_dir)
    return read_parameters_parquet(session_dir / "parameters.parquet", model)


def scan_parameters_parquet(path: str | Path) -> pl.LazyFrame:
    """Lazily scan a parameter Parquet file."""

    return pl.scan_parquet(path)


def validate_parameters(df: pl.DataFrame) -> pl.DataFrame:
    """Validate a queryable session-parameters table."""

    return SessionParametersRow.validate(_with_optional_parameter_columns(df))


def _with_optional_parameter_columns(df: pl.DataFrame) -> pl.DataFrame:
    missing = [name for name in SessionParametersRow.nullable_columns if name not in df.columns]
    additions = [pl.lit(None, dtype=SessionParametersRow.dtypes[name]).alias(name) for name in missing]
    recasts = [
        pl.col(name).cast(SessionParametersRow.dtypes[name], strict=False).alias(name)
        for name in SessionParametersRow.nullable_columns
        if name in df.columns
    ]
    if not additions and not recasts:
        return df
    return df.with_columns([*additions, *recasts])
