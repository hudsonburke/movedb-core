"""Helpers for movedb Parquet metadata envelopes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Annotated

import polars as pl
from pydantic import BaseModel, Discriminator, TypeAdapter

from ..core import AnalogMeta, ForceplateMeta, MarkerMeta

SignalMeta = Annotated[
    MarkerMeta | AnalogMeta | ForceplateMeta,
    Discriminator("type"),
]

_SIGNAL_META_ADAPTER = TypeAdapter(SignalMeta)


class StorageMetadata(BaseModel):
    """Top-level metadata envelope stored in Parquet key-value metadata."""

    schema_name: str
    schema_version: str = "0.1.0"
    format: str
    signal_type: str | None = None
    metadata: dict[str, Any] | None = None


def encode_storage_metadata(metadata: StorageMetadata | dict[str, Any] | None) -> dict[str, str] | None:
    """Encode movedb metadata for Parquet key-value storage."""

    if metadata is None:
        return None
    payload = metadata.model_dump(mode="json") if isinstance(metadata, StorageMetadata) else metadata
    return {"movedb": json.dumps(payload)}


def read_storage_metadata(path: Path | str) -> StorageMetadata | None:
    """Read and validate movedb metadata from a Parquet file."""

    file_meta = pl.read_parquet_metadata(path)
    raw = file_meta.get("movedb")
    if raw is None:
        return None
    payload = json.loads(raw)
    if "schema_name" not in payload or "format" not in payload:
        signal_type = payload.get("type")
        payload = {
            "schema_name": signal_type or "table",
            "format": "wide",
            "signal_type": signal_type,
            "metadata": payload,
        }
    return StorageMetadata.model_validate(payload)


def parse_signal_metadata(metadata: StorageMetadata | None) -> MarkerMeta | AnalogMeta | ForceplateMeta | None:
    """Parse the embedded signal metadata payload, if present."""

    if metadata is None or metadata.metadata is None:
        return None
    return _SIGNAL_META_ADAPTER.validate_python(metadata.metadata)
