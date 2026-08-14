"""C3D and B3D adapters for ingestion."""
from .c3d import read_markers, read_forceplates, read_events, read_parameters

__all__ = ["read_markers", "read_forceplates", "read_events", "read_parameters"]
