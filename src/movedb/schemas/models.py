"""Patito schema definitions for motion capture data.

These models define the column types and validation for Parquet files.
Applications can extend schemas using .with_fields() for extra columns.

Schema hierarchy:
    - TrialMetadata: Base identity for all trial-level records
    - *Data schemas: Pure C3D data (adapter output, no metadata)
    - Composed schemas: TrialMetadata + data (ingestion/cataloging)
    - Parameters: Extensible schema for trial-level PROCESSING parameters
"""

from __future__ import annotations

import patito as pt


# ---------------------------------------------------------------------------
# Base metadata — shared by all trial-level schemas
# ---------------------------------------------------------------------------


class TrialMetadata(pt.Model):
    """Base identity for all trial-level records.

    Every C3D file belongs to a trial within a session for a subject.
    This schema captures that identity and is inherited by Markers,
    Forceplates, Events, and Parameters.
    """

    trial_name: str
    subject_id: str
    session_id: str


# ---------------------------------------------------------------------------
# Pure data schemas — adapter output, no metadata
# ---------------------------------------------------------------------------


class MarkersData(pt.Model):
    """Marker positions without metadata.

    One row per (frame, marker) combination.
    Returned directly by read_markers().
    """

    frame: int
    time: float
    marker_name: str
    x: float
    y: float
    z: float


class ForceplatesData(pt.Model):
    """Force plate data without metadata.

    One row per (frame, plate, variable, axis) combination.
    Returned directly by read_forceplates().
    """

    frame: int
    time: float
    fp_name: str
    variable: str  # force, moment, cop
    axis: str  # x, y, z
    value: float


class EventsData(pt.Model):
    """Gait events without metadata.

    Returned directly by read_events().
    """

    context: str  # Left, Right
    label: str  # Foot Strike, Foot Off
    time: float


# ---------------------------------------------------------------------------
# Composed schemas — TrialMetadata + data for ingestion and cataloging
# ---------------------------------------------------------------------------


class Markers(TrialMetadata, MarkersData):
    """Marker positions with trial metadata.

    Used for Parquet ingestion and catalog queries.
    Inherits frame, time, marker_name, x, y, z from MarkersData
    and trial_name, subject_id, session_id from TrialMetadata.
    """


class Forceplates(TrialMetadata, ForceplatesData):
    """Force plate data with trial metadata.

    Used for Parquet ingestion and catalog queries.
    Inherits frame, time, fp_name, variable, axis, value from ForceplatesData
    and trial_name, subject_id, session_id from TrialMetadata.
    """


class Events(TrialMetadata, EventsData):
    """Gait events with trial metadata.

    Used for Parquet ingestion and catalog queries.
    Inherits context, label, time from EventsData
    and trial_name, subject_id, session_id from TrialMetadata.
    """


# ---------------------------------------------------------------------------
# Parameters — extensible trial-level PROCESSING parameters
# ---------------------------------------------------------------------------


class Parameters(TrialMetadata):
    """Trial-level PROCESSING parameters from C3D files.

    Each C3D file contains parameters (e.g. Mass, bone lengths) that
    are typically consistent across trials in a session but can differ.

    Applications extend with .with_fields() for use-case specific parameters::

        RatParameters = Parameters.with_fields(Mass=float, RFemurLength=float, ...)
    """
