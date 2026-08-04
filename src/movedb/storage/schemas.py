"""Patito models for stable tabular storage contracts."""

from __future__ import annotations

from pathlib import Path

import patito as pt
import polars as pl
from pydantic import ConfigDict


class Vec3(pt.Model):
    """Generic XYZ vector struct used in multiple places."""

    x: float
    y: float
    z: float


class SessionIdentityRow(pt.Model):
    """Optional identity columns carried by session-level tables."""

    subject_id: str | None = None
    session_id: str | None = None
    trial_name: str
    frame: int
    time: float


class SessionWideRow(pt.Model):
    """Base columns shared by wide session-level signal tables."""

    model_config = ConfigDict(extra="allow")

    subject_id: str | None = None
    session_id: str | None = None
    trial_name: str
    frame: int
    time: float


class SessionWideRowWithIdentity(pt.Model):
    """Base columns for wide tables when session identity is required."""

    model_config = ConfigDict(extra="allow")

    subject_id: str
    session_id: str
    trial_name: str
    frame: int
    time: float


class MarkerWideValue(Vec3):
    """Struct payload for one marker column in wide format."""

    residual: float | None = None


class ForceplateWideValue(pt.Model):
    """Struct payload for one forceplate column in wide format."""

    force: Vec3
    moment: Vec3
    cop: Vec3
    free_moment: Vec3 | None = None


class MarkerLongRow(SessionIdentityRow, Vec3):
    """Long-format marker row."""

    marker_name: str
    residual: float | None = None

    @classmethod
    def from_parquet(cls, path: Path | str) -> pl.DataFrame:
        return validate_df(pl.read_parquet(path), cls)

    @classmethod
    def scan(cls, path: Path | str) -> pl.LazyFrame:
        return _scan_validated(path, cls)


class AnalogLongRow(SessionIdentityRow):
    """Long-format analog row."""

    channel_name: str
    value: float
    unit: str | None = None

    @classmethod
    def from_parquet(cls, path: Path | str) -> pl.DataFrame:
        return validate_df(pl.read_parquet(path), cls)

    @classmethod
    def scan(cls, path: Path | str) -> pl.LazyFrame:
        return _scan_validated(path, cls)


class ForceplateLongRow(SessionIdentityRow):
    """Long-format forceplate row."""

    fp_name: str
    variable: str
    axis: str
    value: float

    @classmethod
    def from_parquet(cls, path: Path | str) -> pl.DataFrame:
        return validate_df(pl.read_parquet(path), cls)

    @classmethod
    def scan(cls, path: Path | str) -> pl.LazyFrame:
        return _scan_validated(path, cls)


class EventRow(pt.Model):
    """Event row shared by trial and session exports."""

    subject_id: str | None = None
    session_id: str | None = None
    trial_name: str
    context: str
    label: str
    frame: int | None = None
    time: float | None = None
    description: str | None = None

    @classmethod
    def from_parquet(cls, path: Path | str) -> pl.DataFrame:
        return validate_df(pl.read_parquet(path), cls)

    @classmethod
    def scan(cls, path: Path | str) -> pl.LazyFrame:
        return _scan_validated(path, cls)


class SessionParametersRow(pt.Model):
    """Flat session-parameter row used for queryable Parquet storage."""

    model_config = ConfigDict(extra="allow")

    subject_id: str | None = None
    session_id: str | None = None
    source_file: str | None = None
    parameter_schema: str
    parameter_schema_version: str
    extras_json: str | None = None

    @classmethod
    def from_parquet(cls, path: Path | str) -> pl.DataFrame:
        return validate_df(pl.read_parquet(path), cls)

    @classmethod
    def scan(cls, path: Path | str) -> pl.LazyFrame:
        return _scan_validated(path, cls)


def validate_df(df: pl.DataFrame, model: type[pt.Model]) -> pl.DataFrame:
    """Validate a DataFrame, auto-filling missing nullable columns.

    This is the standard entry point for validating DataFrames against a
    patito model.  Missing nullable columns are injected as typed nulls and
    existing nullable columns are recast to the model's expected dtype before
    ``model.validate()`` is called.
    """
    return model.validate(_with_optional_columns(df, model))


def _scan_validated(path: Path | str, model: type[pt.Model]) -> pl.LazyFrame:
    lazy = pl.scan_parquet(path)
    schema = lazy.collect_schema()
    missing_required = [col for col in model.non_nullable_columns if col not in schema]
    if missing_required:
        raise ValueError(
            f"Missing required columns for {model.__name__}: {', '.join(missing_required)}."
        )
    return lazy


def _with_optional_columns(df: pl.DataFrame, model: type[pt.Model]) -> pl.DataFrame:
    missing = [name for name in model.nullable_columns if name not in df.columns]
    additions = [pl.lit(None, dtype=model.dtypes[name]).alias(name) for name in missing]
    recasts = [
        pl.col(name).cast(model.dtypes[name], strict=False).alias(name)
        for name in model.nullable_columns
        if name in df.columns
    ]
    if not additions and not recasts:
        return df
    return df.with_columns([*additions, *recasts])
