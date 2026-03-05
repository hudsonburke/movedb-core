"""
SQLModel-based database models for MoveDB.

This module contains the ORM layer for persisting biomechanical data
in a relational database. These models are separate from the core
Pydantic data models used in the ingest/export pipeline.
"""

from .groups import (
    CaptureSessionGroup,
    CaptureSessionGroupLink,
    SubjectGroup,
    SubjectGroupLink,
    TrialGroup,
    TrialGroupLink,
)
from .hierarchy import (
    CaptureSession,
    Subject,
    SubjectSessionParameters,
    TrialSubjectLink,
)
from .trial import Trial
from .events import Event
from .files import File

__all__ = [
    "CaptureSession",
    "CaptureSessionGroup",
    "CaptureSessionGroupLink",
    "Event",
    "File",
    "Subject",
    "SubjectGroup",
    "SubjectGroupLink",
    "SubjectSessionParameters",
    "Trial",
    "TrialGroup",
    "TrialGroupLink",
    "TrialSubjectLink",
]
