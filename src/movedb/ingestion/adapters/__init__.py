"""C3D and B3D adapters for ingestion."""
from .c3d import (
    read_points,
    read_markers,  # backward compat alias
    read_forceplates,
    read_forceplate_geometry,
    read_analogs,
    read_events,
    read_parameters,
)

__all__ = [
    "read_points",
    "read_markers",
    "read_forceplates",
    "read_forceplate_geometry",
    "read_analogs",
    "read_events",
    "read_parameters",
]
