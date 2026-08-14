"""Patito schema definitions for motion capture data."""

from .models import (
    TrialMetadata,
    Points,
    PointsData,
    Forceplates,
    ForceplatesData,
    ForceplateGeometry,
    ForceplateGeometryData,
    Analogs,
    AnalogsData,
    Events,
    EventsData,
    Parameters,
)

__all__ = [
    "TrialMetadata",
    "Points", "PointsData",
    "Forceplates", "ForceplatesData",
    "ForceplateGeometry", "ForceplateGeometryData",
    "Analogs", "AnalogsData",
    "Events", "EventsData",
    "Parameters",
]
