"""Validation helpers for movedb wide and long storage tables."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, cast

import polars as pl
import patito as pt
from pydantic import create_model

from ..core import AnalogMeta, ForceplateMeta, MarkerMeta
from .schemas import (
    AnalogLongRow,
    EventRow,
    ForceplateLongRow,
    ForceplateWideValue,
    MarkerLongRow,
    MarkerWideValue,
    SessionWideRow,
    SessionWideRowWithIdentity,
)
_NUMERIC_DTYPES = {
    pl.Float32,
    pl.Float64,
    pl.Int8,
    pl.Int16,
    pl.Int32,
    pl.Int64,
    pl.UInt8,
    pl.UInt16,
    pl.UInt32,
    pl.UInt64,
}

DynamicFieldDefinition = tuple[Any, object]


def validate_marker_long(df: pl.DataFrame) -> pl.DataFrame:
    return _validate_tabular(df, MarkerLongRow)


def validate_analog_long(df: pl.DataFrame) -> pl.DataFrame:
    return _validate_tabular(df, AnalogLongRow)


def validate_forceplate_long(df: pl.DataFrame) -> pl.DataFrame:
    return _validate_tabular(df, ForceplateLongRow)


def validate_events(df: pl.DataFrame) -> pl.DataFrame:
    return _validate_tabular(df, EventRow)


def validate_markers_wide(
    df: pl.DataFrame, metadata: MarkerMeta, *, require_identity: bool = False
) -> pl.DataFrame:
    return _validate_wide(
        df,
        metadata.names,
        kind="markers",
        require_identity=require_identity,
    )


def validate_analogs_wide(
    df: pl.DataFrame, metadata: AnalogMeta, *, require_identity: bool = False
) -> pl.DataFrame:
    return _validate_wide(
        df,
        metadata.names,
        kind="analogs",
        require_identity=require_identity,
    )


def validate_forceplates_wide(
    df: pl.DataFrame, metadata: ForceplateMeta, *, require_identity: bool = False
) -> pl.DataFrame:
    return _validate_wide(
        df,
        metadata.names,
        kind="forceplates",
        require_identity=require_identity,
    )


def _validate_tabular(df: pl.DataFrame, model: type[pt.Model]) -> pl.DataFrame:
    return model.validate(_with_optional_columns(df, model))


def _validate_wide(
    df: pl.DataFrame,
    names: list[str],
    *,
    kind: str,
    require_identity: bool,
) -> pl.DataFrame:
    normalized = _normalize_wide(df, names, kind=kind)
    model = _create_dynamic_wide_model(kind, tuple(names), require_identity=require_identity)
    return _validate_tabular(normalized, model)


@lru_cache(maxsize=None)
def _create_dynamic_wide_model(
    kind: str,
    names: tuple[str, ...],
    *,
    require_identity: bool,
) -> type[pt.Model]:
    base_model = SessionWideRowWithIdentity if require_identity else SessionWideRow
    model_name, field_type = _wide_model_spec(kind)
    field_definitions: dict[str, DynamicFieldDefinition] = {
        name: (field_type | None, ...) for name in names
    }
    kwargs: dict[str, Any] = {"__base__": base_model, **field_definitions}
    return cast(type[pt.Model], create_model(model_name, **kwargs))


def _wide_model_spec(kind: str) -> tuple[str, Any]:
    if kind == "markers":
        return "MarkerWideRow", MarkerWideValue
    if kind == "analogs":
        return "AnalogWideRow", float
    if kind == "forceplates":
        return "ForceplateWideRow", ForceplateWideValue
    raise ValueError(f"Unsupported wide validation kind: {kind}")


def _normalize_wide(df: pl.DataFrame, columns: list[str], *, kind: str) -> pl.DataFrame:
    if kind == "markers":
        return _normalize_struct_field(df, columns, field_name="residual")
    if kind == "analogs":
        return _cast_numeric_columns(df, columns)
    if kind == "forceplates":
        free_moment_struct = pl.struct(
            pl.lit(None, dtype=pl.Float64).alias("x"),
            pl.lit(None, dtype=pl.Float64).alias("y"),
            pl.lit(None, dtype=pl.Float64).alias("z"),
        ).alias("free_moment")
        return _normalize_struct_field(df, columns, field_name="free_moment", value=free_moment_struct)
    raise ValueError(f"Unsupported wide normalization kind: {kind}")


def _normalize_struct_field(
    df: pl.DataFrame,
    columns: list[str],
    *,
    field_name: str,
    value: pl.Expr | None = None,
) -> pl.DataFrame:
    expressions = []
    field_value = value if value is not None else pl.lit(None, dtype=pl.Float64).alias(field_name)
    for name in columns:
        if name not in df.columns:
            continue
        dtype = df.schema[name]
        if not isinstance(dtype, pl.Struct):
            continue
        field_names = {field.name for field in dtype.fields}
        if field_name not in field_names:
            expressions.append(
                pl.col(name)
                .struct.with_fields(field_value)
                .alias(name)
            )
    if not expressions:
        return df
    return df.with_columns(expressions)


def _cast_numeric_columns(df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
    expressions = []
    for name in columns:
        if name not in df.columns:
            continue
        dtype = df.schema[name]
        if dtype in _NUMERIC_DTYPES and dtype != pl.Float64:
            expressions.append(pl.col(name).cast(pl.Float64, strict=False).alias(name))
    if not expressions:
        return df
    return df.with_columns(expressions)


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
