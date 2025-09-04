"""
Validation utilities for movedb.

This module provides functions for validating biomechanical data,
including gap detection, data quality assessment, and trial validation.
"""

from .gaps import (
    GapInfo,
    MarkerGapResult,
    TrialGapResult,
    detect_marker_gaps,
    detect_trial_gaps,
    find_markers_with_gaps,
)

__all__ = [
    "GapInfo",
    "MarkerGapResult", 
    "TrialGapResult",
    "detect_marker_gaps",
    "detect_trial_gaps",
    "find_markers_with_gaps",
]
