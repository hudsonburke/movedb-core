"""
MoveDB: A comprehensive library for movement database operations.

MoveDB provides tools for:
- C3D file I/O and processing
- Biomechanical data analysis
- OpenSim integration and analysis
- Motion capture data management
- Force platform data processing
"""

# Core modules
from . import models
from . import ingest
from . import visualize
from . import storage

# Validation module (depends on legacy models - deprecated)
try:
    from . import validation
    _HAS_VALIDATION = True
except (ImportError, ModuleNotFoundError):
    _HAS_VALIDATION = False

# OpenSim integration
try:
    from . import osim
    _HAS_OSIM = True
except Exception:
    # OpenSim module not available (likely due to missing OpenSim installation or dependencies)
    _HAS_OSIM = False
    osim = None

# Version info
__version__ = "0.3.4"

# Package info
__author__ = "Hudson Burke"
__email__ = "hudsonburke01@gmail.com"

# Check OpenSim availability
def has_opensim() -> bool:
    """Check if OpenSim integration is available."""
    return _HAS_OSIM

# Main exports
__all__ = [
    "models",
    "ingest",
    "visualize",
    "validation",
    "osim",
    "has_opensim",
    "__version__",
    "__author__",
    "__email__"
]
