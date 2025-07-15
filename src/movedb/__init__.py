"""
MoveDB Core - Movement Database Core Library

A Python library for handling movement/biomechanics data including:
- C3D file I/O operations
- OpenSim integration
- Time series data processing
- Motion capture data management
"""

__version__ = "0.3.4"
__author__ = "Hudson Burke"
__email__ = "hudsonburke01@gmail.com"

# Import main classes for easy access
from .core import (
    MISSING,
    MISSING_LIST,
    UNSET,
    AnalogChannel,
    Analogs,
    Event,
    EZForcePlatform,
    MarkerTrajectory,
    Points,
    Sentinel,
    TimeSeriesGroup,
    Trial,
)
from .file_io import parse_enf_file, sto_to_df
from .utils import snake_to_pascal

# Conditionally import API module
# try:
# from . import api
# _API_AVAILABLE = True
# except ImportError:
# _API_AVAILABLE = False

__all__ = [
    # Core classes
    "Trial",
    "Event",
    "Points",
    "Analogs",
    "MarkerTrajectory",
    "AnalogChannel",
    "EZForcePlatform",
    "TimeSeriesGroup",
    # Sentinels
    "Sentinel",
    "MISSING",
    "MISSING_LIST",
    "UNSET",
    # File I/O
    "sto_to_df",
    "parse_enf_file",
    # Utilities
    "snake_to_pascal",
]

# Add API to __all__ if available
# if _API_AVAILABLE:
#     __all__.append("api")
