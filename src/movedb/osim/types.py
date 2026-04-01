"""OpenSim artifact row schema and pipeline parameter types."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TypedDict


class OsimArtifactRow(TypedDict):
    """Schema for a row in the osim_artifacts table."""

    artifact_id: str
    run_id: str
    pipeline: str
    output_kind: str
    scope: str
    session_key: str
    trial_key: str | None
    path: str
    native_path: str | None
    format: str
    status: str
    is_canonical: bool
    created_at: str
    parameter_hash: str
    parameter_json: str
    provenance_json: str | None
    extras_json: str | None


class IKParameters(TypedDict):
    """Parameters for inverse kinematics pipeline."""

    ik_setup_path: str
    model_path: str
    t_start: float
    t_end: float


class IDParameters(TypedDict):
    """Parameters for inverse dynamics pipeline."""

    model_path: str
    external_loads_path: str
    lowpass_cutoff: float | None
    t_start: float
    t_end: float


class SOParameters(TypedDict):
    """Parameters for static optimization pipeline."""

    model_path: str
    actuator_set: str | None
    t_start: float
    t_end: float


class ScaleParameters(TypedDict):
    """Parameters for scaling pipeline."""

    model_path: str
    mass_kg: float
    marker_set: str | None


class CMCParameters(TypedDict):
    """Parameters for computed muscle control pipeline."""

    model_path: str
    t_start: float
    t_end: float


def make_artifact_id() -> str:
    """Generate a new artifact ID.
    
    Returns:
        UUID4 string (36 characters with hyphens).
    """
    return str(uuid.uuid4())


def make_provenance(tool_version: str, command: str) -> str:
    """Generate a provenance record in canonical JSON format.
    
    Args:
        tool_version: Tool/library version string (e.g., "osimpy-0.1.0").
        command: Command or function name that was executed.
    
    Returns:
        Canonical JSON string with tool_version, timestamp, and command.
    """
    provenance = {
        "tool_version": tool_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
    }
    return json.dumps(provenance, sort_keys=True, separators=(",", ":"), allow_nan=False)
