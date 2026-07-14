"""Validation helpers for movedb wide storage tables."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, cast

import polars as pl
import patito as pt
from pydantic import create_model

from ..core import AnalogMeta, ForceplateMeta, MarkerMeta
from .schemas import (
    ForceplateWideValue,
    MarkerWideValue,
    SessionWideRow,
    SessionWideRowWithIdentity,
    validate_df,
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


def validate_markers_wide(
    df: pl.DataFrame, metadata: MarkerMeta, *, require_identity: bool = False
) -> pl.DataFrame:
    normalized = _normalize_struct_field(df, metadata.names, field_name="residual")
    model = _create_dynamic_wide_model(
        "MarkerWideRow", MarkerWideValue, tuple(metadata.names), require_identity=require_identity,
    )
    return validate_df(normalized, model)


def validate_analogs_wide(
    df: pl.DataFrame, metadata: AnalogMeta, *, require_identity: bool = False
) -> pl.DataFrame:
    normalized = _cast_numeric_columns(df, metadata.names)
    model = _create_dynamic_wide_model(
        "AnalogWideRow", float, tuple(metadata.names), require_identity=require_identity,
    )
    return validate_df(normalized, model)


def validate_forceplates_wide(
    df: pl.DataFrame, metadata: ForceplateMeta, *, require_identity: bool = False
) -> pl.DataFrame:
    free_moment_struct = pl.struct(
        pl.lit(None, dtype=pl.Float64).alias("x"),
        pl.lit(None, dtype=pl.Float64).alias("y"),
        pl.lit(None, dtype=pl.Float64).alias("z"),
    ).alias("free_moment")
    normalized = _normalize_struct_field(
        df, metadata.names, field_name="free_moment", value=free_moment_struct,
    )
    model = _create_dynamic_wide_model(
        "ForceplateWideRow", ForceplateWideValue, tuple(metadata.names), require_identity=require_identity,
    )
    return validate_df(normalized, model)


@lru_cache(maxsize=None)
def _create_dynamic_wide_model(
    model_name: str,
    field_type: Any,
    names: tuple[str, ...],
    *,
    require_identity: bool,
) -> type[pt.Model]:
    base_model = SessionWideRowWithIdentity if require_identity else SessionWideRow
    field_definitions: dict[str, DynamicFieldDefinition] = {
        name: (field_type | None, ...) for name in names
    }
    kwargs: dict[str, Any] = {"__base__": base_model, **field_definitions}
    return cast(type[pt.Model], create_model(model_name, **kwargs))


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
