"""Patito schema definitions for motion capture data.

These models define the column types and validation for Parquet files.
Applications can extend schemas using .with_fields() for extra columns.

Schema hierarchy:
    - TrialMetadata: Base identity for all trial-level records
    - *Data schemas: Pure C3D data (adapter output, no metadata)
    - Composed schemas: TrialMetadata + data (ingestion/cataloging)
    - Parameters: Extensible schema for trial-level parameters
"""

from __future__ import annotations

import polars as pl
import patito as pt


# ---------------------------------------------------------------------------
# Base metadata — shared by all trial-level schemas
# ---------------------------------------------------------------------------


class TrialMetadata(pt.Model):
    """Base identity for all trial-level records.

    Every C3D file belongs to a trial within a session for a subject.
    This schema captures that identity and is inherited by Points,
    Forceplates, Events, ForceplateGeometry, Analogs, and Parameters.
    """

    trial_name: str
    subject_id: str
    session_id: str


# ---------------------------------------------------------------------------
# Pure data schemas — adapter output, no metadata
# ---------------------------------------------------------------------------


class PointsData(pt.Model):
    """3D point positions without metadata.

    One row per (frame, marker) combination.
    Returned directly by read_points().

    Includes residual (tracking error) and camera_mask (which cameras
    saw the marker) for data quality filtering.
    """

    frame: int
    time: float
    marker_name: str
    x: float
    y: float
    z: float
    residual: float
    camera_mask: list[int]


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


class ForceplateGeometryData(pt.Model):
    """Force plate calibration and positioning without metadata.

    One row per plate per trial.
    Returned directly by read_forceplate_geometry().

    Origin is a 3D point (list of 3 floats).
    Corners is a flattened 3x4 array (12 floats).
    Cal_matrix is a flattened 6x6 array (36 floats).
    """

    fp_name: str
    origin: list[float]
    corners: list[float]
    cal_matrix: list[float]


class AnalogsData(pt.Model):
    """Raw analog channel data without metadata.

    One row per (frame, channel) combination.
    Returned directly by read_analogs().
    """

    frame: int
    time: float
    channel_name: str
    value: float
    unit: str


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


class Points(TrialMetadata, PointsData):
    """3D point positions with trial metadata.

    Used for Parquet ingestion and catalog queries.
    Inherits frame, time, marker_name, x, y, z, residual, camera_mask
    from PointsData and trial_name, subject_id, session_id from TrialMetadata.
    """


class Forceplates(TrialMetadata, ForceplatesData):
    """Force plate data with trial metadata.

    Used for Parquet ingestion and catalog queries.
    Inherits frame, time, fp_name, variable, axis, value from ForceplatesData
    and trial_name, subject_id, session_id from TrialMetadata.
    """


class ForceplateGeometry(TrialMetadata, ForceplateGeometryData):
    """Force plate calibration with trial metadata.

    Used for Parquet ingestion and catalog queries.
    Inherits fp_name, origin, corners, cal_matrix from ForceplateGeometryData
    and trial_name, subject_id, session_id from TrialMetadata.
    """


class Analogs(TrialMetadata, AnalogsData):
    """Raw analog channels with trial metadata.

    Used for Parquet ingestion and catalog queries.
    Inherits frame, time, channel_name, value, unit from AnalogsData
    and trial_name, subject_id, session_id from TrialMetadata.
    """


class Events(TrialMetadata, EventsData):
    """Gait events with trial metadata.

    Used for Parquet ingestion and catalog queries.
    Inherits context, label, time from EventsData
    and trial_name, subject_id, session_id from TrialMetadata.
    """


# ---------------------------------------------------------------------------
# Parameters — extensible trial-level parameters
# ---------------------------------------------------------------------------


class Parameters(TrialMetadata):
    """Trial-level parameters from C3D files.

    Each C3D file contains PROCESSING parameters (e.g. Mass, bone lengths),
    TRIAL parameters (e.g. camera rate, coordinate directions), and
    ANALYSIS parameters. These are typically consistent across trials
    in a session but can differ.

    Applications extend with .with_fields() for use-case specific parameters::

        RatParameters = Parameters.with_fields(Mass=float, RFemurLength=float, ...)
    """
