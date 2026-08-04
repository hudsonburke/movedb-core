"""Tests for manifest Parquet I/O operations."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from movedb.osim.manifest import append_to_manifest, read_manifest, write_manifest
from movedb.osim.types import OsimArtifactRow, make_artifact_id


def test_write_empty_list_read_back_returns_empty_list(tmp_path: Path) -> None:
    """Writing an empty list and reading back should return empty list."""
    manifest_path = tmp_path / "manifest.parquet"
    
    write_manifest(manifest_path, [])
    result = read_manifest(manifest_path)
    
    assert result == []


def test_write_three_artifacts_read_back_all_fields_preserved(tmp_path: Path) -> None:
    """Writing 3 artifacts should preserve all fields on read, including None values."""
    manifest_path = tmp_path / "manifest.parquet"
    
    artifacts = [
        OsimArtifactRow(
            artifact_id=make_artifact_id(),
            run_id="a" * 64,
            pipeline="ik",
            output_kind="ik_positions",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk01",
            path="runs/aabbccdd11/Walk01_ik.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T12:00:00Z",
            parameter_hash="b" * 64,
            parameter_json='{"accuracy":1e-5}',
            provenance_json=None,
            extras_json=None,
        ),
        OsimArtifactRow(
            artifact_id=make_artifact_id(),
            run_id="c" * 64,
            pipeline="id",
            output_kind="id_forces",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk02",
            path="runs/ccddeeff22/Walk02_id.parquet",
            native_path="/path/to/native.c3d",
            format="parquet",
            status="complete",
            is_canonical=False,
            created_at="2026-03-31T13:00:00Z",
            parameter_hash="d" * 64,
            parameter_json='{"lowpass":6.0}',
            provenance_json='{"tool_version":"osimpy-0.1.0"}',
            extras_json='{"metadata":"value"}',
        ),
        OsimArtifactRow(
            artifact_id=make_artifact_id(),
            run_id="e" * 64,
            pipeline="so",
            output_kind="so_activations",
            scope="session",
            session_key="sub-02/ses-03",
            trial_key=None,
            path="runs/eeff99aa33/SO_results.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T14:00:00Z",
            parameter_hash="f" * 64,
            parameter_json='{}',
            provenance_json=None,
            extras_json=None,
        ),
    ]
    
    write_manifest(manifest_path, artifacts)
    result = read_manifest(manifest_path)
    
    assert len(result) == 3
    # Check first artifact
    assert result[0]["pipeline"] == "ik"
    assert result[0]["trial_key"] == "sub-01/ses-01/Walk01"
    assert result[0]["native_path"] is None
    assert result[0]["provenance_json"] is None
    assert result[0]["is_canonical"] is True
    
    # Check second artifact
    assert result[1]["pipeline"] == "id"
    assert result[1]["native_path"] == "/path/to/native.c3d"
    assert result[1]["provenance_json"] == '{"tool_version":"osimpy-0.1.0"}'
    assert result[1]["is_canonical"] is False
    
    # Check third artifact
    assert result[2]["trial_key"] is None
    assert result[2]["scope"] == "session"


def test_read_from_nonexistent_path_returns_empty_list(tmp_path: Path) -> None:
    """Reading from a non-existent manifest path should return empty list, not raise error."""
    manifest_path = tmp_path / "does_not_exist" / "manifest.parquet"
    
    result = read_manifest(manifest_path)
    
    assert result == []


def test_append_two_to_existing_three_returns_five_total(tmp_path: Path) -> None:
    """Appending 2 artifacts to existing 3 should result in 5 total."""
    manifest_path = tmp_path / "manifest.parquet"
    
    initial = [
        OsimArtifactRow(
            artifact_id="id-1",
            run_id="a" * 64,
            pipeline="ik",
            output_kind="ik_positions",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk01",
            path="run1/Walk01_ik.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T12:00:00Z",
            parameter_hash="b" * 64,
            parameter_json='{}',
            provenance_json=None,
            extras_json=None,
        ),
        OsimArtifactRow(
            artifact_id="id-2",
            run_id="c" * 64,
            pipeline="ik",
            output_kind="ik_positions",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk02",
            path="run1/Walk02_ik.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T12:10:00Z",
            parameter_hash="d" * 64,
            parameter_json='{}',
            provenance_json=None,
            extras_json=None,
        ),
        OsimArtifactRow(
            artifact_id="id-3",
            run_id="e" * 64,
            pipeline="id",
            output_kind="id_forces",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk01",
            path="run2/Walk01_id.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T13:00:00Z",
            parameter_hash="f" * 64,
            parameter_json='{}',
            provenance_json=None,
            extras_json=None,
        ),
    ]
    
    write_manifest(manifest_path, initial)
    
    new_artifacts = [
        OsimArtifactRow(
            artifact_id="id-4",
            run_id="g" * 64,
            pipeline="so",
            output_kind="so_activations",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk01",
            path="run3/Walk01_so.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T14:00:00Z",
            parameter_hash="h" * 64,
            parameter_json='{}',
            provenance_json=None,
            extras_json=None,
        ),
        OsimArtifactRow(
            artifact_id="id-5",
            run_id="i" * 64,
            pipeline="so",
            output_kind="so_activations",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk02",
            path="run3/Walk02_so.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T14:10:00Z",
            parameter_hash="j" * 64,
            parameter_json='{}',
            provenance_json=None,
            extras_json=None,
        ),
    ]
    
    append_to_manifest(manifest_path, new_artifacts)
    result = read_manifest(manifest_path)
    
    assert len(result) == 5


def test_append_with_duplicate_artifact_id_deduplicates_latest_wins(tmp_path: Path) -> None:
    """Appending artifacts with duplicate artifact_id should use latest (new one) not existing."""
    manifest_path = tmp_path / "manifest.parquet"
    
    initial = [
        OsimArtifactRow(
            artifact_id="dup-id",
            run_id="a" * 64,
            pipeline="ik",
            output_kind="ik_positions",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk01",
            path="run1/Walk01_ik.parquet",
            native_path=None,
            format="parquet",
            status="incomplete",
            is_canonical=False,
            created_at="2026-03-31T12:00:00Z",
            parameter_hash="b" * 64,
            parameter_json='{"old":"value"}',
            provenance_json=None,
            extras_json=None,
        ),
    ]
    
    write_manifest(manifest_path, initial)
    
    new_artifacts = [
        OsimArtifactRow(
            artifact_id="dup-id",
            run_id="b" * 64,
            pipeline="id",
            output_kind="id_forces",
            scope="trial",
            session_key="sub-01/ses-01",
            trial_key="sub-01/ses-01/Walk01",
            path="run2/Walk01_id.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T13:00:00Z",
            parameter_hash="c" * 64,
            parameter_json='{"new":"value"}',
            provenance_json=None,
            extras_json=None,
        ),
    ]
    
    append_to_manifest(manifest_path, new_artifacts)
    result = read_manifest(manifest_path)
    
    assert len(result) == 1
    assert result[0]["artifact_id"] == "dup-id"
    assert result[0]["pipeline"] == "id"  # new value
    assert result[0]["parameter_json"] == '{"new":"value"}'  # new value
    assert result[0]["status"] == "complete"  # new value
    assert result[0]["is_canonical"] is True  # new value


def test_roundtrip_preserves_none_fields(tmp_path: Path) -> None:
    """Round-trip write/read should preserve None fields as None, not convert to empty string or NaN."""
    manifest_path = tmp_path / "manifest.parquet"
    
    artifacts = [
        OsimArtifactRow(
            artifact_id=make_artifact_id(),
            run_id="a" * 64,
            pipeline="ik",
            output_kind="ik_positions",
            scope="session",
            session_key="sub-01/ses-01",
            trial_key=None,
            path="runs/aabbccdd/results.parquet",
            native_path=None,
            format="parquet",
            status="complete",
            is_canonical=True,
            created_at="2026-03-31T12:00:00Z",
            parameter_hash="b" * 64,
            parameter_json='{}',
            provenance_json=None,
            extras_json=None,
        ),
    ]
    
    write_manifest(manifest_path, artifacts)
    result = read_manifest(manifest_path)
    
    assert result[0]["trial_key"] is None
    assert result[0]["native_path"] is None
    assert result[0]["provenance_json"] is None
    assert result[0]["extras_json"] is None
    # Verify they're actually None, not empty strings
    assert not isinstance(result[0]["trial_key"], str)
    assert not isinstance(result[0]["native_path"], str)
