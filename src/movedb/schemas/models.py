"""Patito schema definitions for motion capture data.

These models define the column types and validation for Parquet files.
Applications can extend schemas using .with_fields() for extra columns.
"""

from __future__ import annotations

import patito as pt


class Markers(pt.Model):
    """Marker positions (long format).

    One row per (frame, marker) combination.
    """
    frame: int
    time: float
    marker_name: str
    x: float
    y: float
    z: float
    trial_name: str
    subject_id: str
    session_id: str


class Forceplates(pt.Model):
    """Force plate data (long format).

    One row per (frame, plate, variable, axis) combination.
    """
    frame: int
    time: float
    fp_name: str
    variable: str  # force, moment, cop, free_moment
    axis: str      # x, y, z
    value: float
    trial_name: str
    subject_id: str
    session_id: str


class Events(pt.Model):
    """Gait events.

    One row per event (foot strike / foot off).
    """
    context: str   # Left, Right
    label: str     # Foot Strike, Foot Off
    time: float
    trial_name: str
    subject_id: str
    session_id: str


class Sessions(pt.Model):
    """Per-session anthropometric parameters.

    Extracted from C3D PROCESSING group during conversion.
    """
    subject_id: str
    session_id: str
    Mass: float | None = None
    RFemurLength: float | None = None
    RTibiaLength: float | None = None
    RFootLength: float | None = None
    LFemurLength: float | None = None
    LTibiaLength: float | None = None
    LFootLength: float | None = None
    Length: float | None = None
