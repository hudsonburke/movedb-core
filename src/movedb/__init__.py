"""
MoveDB: A comprehensive library for movement database operations.

MoveDB provides tools for:
- C3D file I/O and processing
- Biomechanical data analysis
- Motion capture data management
- Force platform data processing
"""

from . import core
from . import adapters
from . import storage
from . import catalog


# Main exports
__all__ = [
    "core",
    "adapters",
    "storage",
    "catalog",
]
