"""Patito models for stable tabular storage contracts."""

from __future__ import annotations

import patito as pt
from pydantic import ConfigDict


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


class MarkerWideValue(pt.Model):
    """Struct payload for one marker column in wide format."""

    x: float
    y: float
    z: float
    residual: float | None = None


class ForceplateVector(pt.Model):
    """XYZ vector payload used inside forceplate structs."""

    x: float
    y: float
    z: float


class ForceplateWideValue(pt.Model):
    """Struct payload for one forceplate column in wide format."""

    force: ForceplateVector
    moment: ForceplateVector
    cop: ForceplateVector
    free_moment: ForceplateVector | None = None


class MarkerLongRow(SessionIdentityRow):
    """Long-format marker row."""

    marker_name: str
    x: float
    y: float
    z: float
    residual: float | None = None


class AnalogLongRow(SessionIdentityRow):
    """Long-format analog row."""

    channel_name: str
    value: float
    unit: str | None = None


class ForceplateLongRow(SessionIdentityRow):
    """Long-format forceplate row."""

    fp_name: str
    variable: str
    axis: str
    value: float


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


class SessionParametersRow(pt.Model):
    """Flat session-parameter row used for queryable Parquet storage."""

    model_config = ConfigDict(extra="allow")

    subject_id: str | None = None
    session_id: str | None = None
    source_file: str | None = None
    parameter_schema: str
    parameter_schema_version: str
    extras_json: str | None = None
