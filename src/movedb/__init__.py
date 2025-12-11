"""
MoveDB: A comprehensive library for movement database operations.

MoveDB provides tools for:
- C3D file I/O and processing
- Biomechanical data analysis
- Motion capture data management
- Force platform data processing
"""

from . import core
from . import ingest
from . import visualize
from . import validation


# Main exports
__all__ = [
    "core",
    "ingest",
    "visualize",
    "validation",
]
