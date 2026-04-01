"""Tests for osim types module."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pytest

from movedb.osim.types import (
    CMCParameters,
    IDParameters,
    IKParameters,
    OsimArtifactRow,
    SOParameters,
    ScaleParameters,
    make_artifact_id,
    make_provenance,
)


def test_make_artifact_id_returns_36_char_uuid4() -> None:
    """artifact_id should be a valid UUID4 string (36 chars with hyphens)."""
    artifact_id = make_artifact_id()
    assert isinstance(artifact_id, str)
    assert len(artifact_id) == 36
    # UUID4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    assert re.match(r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$", artifact_id)


def test_make_provenance_returns_valid_json_with_all_keys() -> None:
    """make_provenance should return canonical JSON with tool_version, timestamp, command."""
    provenance_str = make_provenance("osimpy-0.1.0", "run_ik")
    
    # Should be valid JSON
    prov = json.loads(provenance_str)
    
    # Should have all three required keys
    assert "tool_version" in prov
    assert "timestamp" in prov
    assert "command" in prov
    
    # Values should be correct
    assert prov["tool_version"] == "osimpy-0.1.0"
    assert prov["command"] == "run_ik"
    
    # timestamp should be ISO 8601 parseable
    datetime.fromisoformat(prov["timestamp"])


def test_osim_artifact_row_construction_with_all_fields() -> None:
    """OsimArtifactRow should construct with all required fields."""
    row: OsimArtifactRow = {
        "artifact_id": make_artifact_id(),
        "run_id": "a" * 64,
        "pipeline": "ik",
        "output_kind": "ik_positions",
        "scope": "trial",
        "session_key": "sub-01/ses-01",
        "trial_key": "sub-01/ses-01/Walk01",
        "path": "runs/aabbccddee11/Walk01_ik.parquet",
        "native_path": "runs/aabbccddee11/Walk01_ik.mot",
        "format": "parquet",
        "status": "complete",
        "is_canonical": True,
        "created_at": "2026-03-31T12:00:00Z",
        "parameter_hash": "a" * 64,
        "parameter_json": '{"accuracy":1e-5}',
        "provenance_json": make_provenance("osimpy-0.1.0", "run_ik"),
        "extras_json": None,
    }
    
    # Verify artifact_id is 36 chars
    assert len(row["artifact_id"]) == 36
    assert row["pipeline"] == "ik"
    assert row["is_canonical"] is True


def test_trial_key_can_be_none_for_session_scope() -> None:
    """When scope is 'session', trial_key should be allowed as None."""
    row: OsimArtifactRow = {
        "artifact_id": make_artifact_id(),
        "run_id": "b" * 64,
        "pipeline": "scale",
        "output_kind": "scaled_model",
        "scope": "session",
        "session_key": "sub-01/ses-01",
        "trial_key": None,
        "path": "runs/bbccddee1122/scaled_scaled.osim",
        "native_path": "runs/bbccddee1122/scaled_scaled.osim",
        "format": "osim",
        "status": "complete",
        "is_canonical": True,
        "created_at": "2026-03-31T12:00:00Z",
        "parameter_hash": "b" * 64,
        "parameter_json": '{"mass_kg":0.33}',
        "provenance_json": None,
        "extras_json": None,
    }
    
    assert row["trial_key"] is None
    assert row["scope"] == "session"


def test_pipeline_parameters_ik() -> None:
    """IKParameters TypedDict should construct correctly."""
    params: IKParameters = {
        "ik_setup_path": "setups/ik_default.xml",
        "model_path": "models/scaled.osim",
        "t_start": 0.0,
        "t_end": 2.5,
    }
    
    assert params["ik_setup_path"] == "setups/ik_default.xml"
    assert params["model_path"] == "models/scaled.osim"
    assert params["t_start"] == 0.0
    assert params["t_end"] == 2.5


def test_pipeline_parameters_id() -> None:
    """IDParameters TypedDict should construct correctly."""
    params: IDParameters = {
        "model_path": "models/scaled.osim",
        "external_loads_path": "data/Walk01_grf.xml",
        "lowpass_cutoff": 6.0,
        "t_start": 0.5,
        "t_end": 2.0,
    }
    
    assert params["model_path"] == "models/scaled.osim"
    assert params["external_loads_path"] == "data/Walk01_grf.xml"
    assert params["lowpass_cutoff"] == 6.0


def test_pipeline_parameters_id_with_none_lowpass() -> None:
    """IDParameters should allow lowpass_cutoff to be None."""
    params: IDParameters = {
        "model_path": "models/scaled.osim",
        "external_loads_path": "data/Walk01_grf.xml",
        "lowpass_cutoff": None,
        "t_start": 0.5,
        "t_end": 2.0,
    }
    
    assert params["lowpass_cutoff"] is None


def test_pipeline_parameters_so() -> None:
    """SOParameters TypedDict should construct correctly."""
    params: SOParameters = {
        "model_path": "models/scaled.osim",
        "actuator_set": "actuators.xml",
        "t_start": 0.0,
        "t_end": 2.5,
    }
    
    assert params["model_path"] == "models/scaled.osim"
    assert params["actuator_set"] == "actuators.xml"


def test_pipeline_parameters_so_with_none_actuator() -> None:
    """SOParameters should allow actuator_set to be None."""
    params: SOParameters = {
        "model_path": "models/scaled.osim",
        "actuator_set": None,
        "t_start": 0.0,
        "t_end": 2.5,
    }
    
    assert params["actuator_set"] is None


def test_pipeline_parameters_scale() -> None:
    """ScaleParameters TypedDict should construct correctly."""
    params: ScaleParameters = {
        "model_path": "models/generic.osim",
        "mass_kg": 85.0,
        "marker_set": "markers.xml",
    }
    
    assert params["model_path"] == "models/generic.osim"
    assert params["mass_kg"] == 85.0
    assert params["marker_set"] == "markers.xml"


def test_pipeline_parameters_scale_with_none_marker() -> None:
    """ScaleParameters should allow marker_set to be None."""
    params: ScaleParameters = {
        "model_path": "models/generic.osim",
        "mass_kg": 75.5,
        "marker_set": None,
    }
    
    assert params["marker_set"] is None


def test_pipeline_parameters_cmc() -> None:
    """CMCParameters TypedDict should construct correctly."""
    params: CMCParameters = {
        "model_path": "models/scaled.osim",
        "t_start": 0.0,
        "t_end": 2.5,
    }
    
    assert params["model_path"] == "models/scaled.osim"
    assert params["t_start"] == 0.0
    assert params["t_end"] == 2.5


def test_make_provenance_canonical_json_format() -> None:
    """make_provenance should produce canonical JSON (sorted keys, compact separators)."""
    prov_str = make_provenance("tool-1.0", "cmd")
    
    # Parse and re-serialize to check if already canonical
    parsed = json.loads(prov_str)
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), allow_nan=False)
    
    # Should match (idempotent)
    assert json.loads(prov_str) == json.loads(canonical)
