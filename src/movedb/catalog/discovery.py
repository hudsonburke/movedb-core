"""Session-bundle discovery for DuckDB catalog registration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from ..storage import read_storage_metadata


class SessionFileDescriptor(BaseModel):
    """Description of one canonical file inside a session bundle."""

    file_kind: str
    path: str
    schema_name: str | None = None
    format: str | None = None
    signal_type: str | None = None
    metadata_json: str | None = None


class SessionBundleDescriptor(BaseModel):
    """Discovered metadata for a session-level motion bundle."""

    session_dir: str
    subject_id: str | None = None
    session_id: str | None = None
    files: list[SessionFileDescriptor]


_CANONICAL_SESSION_FILES = {
    "markers": "markers.parquet",
    "analogs": "analogs.parquet",
    "forceplates": "forceplates.parquet",
    "events": "events.parquet",
    "parameters": "parameters.parquet",
    "kinematics": "kinematics.parquet",
    "grf": "grf.parquet",
}


def discover_session_bundle(session_dir: str | Path) -> SessionBundleDescriptor:
    """Inspect a session motion directory and describe its canonical artifacts."""

    session_path = Path(session_dir)
    files: list[SessionFileDescriptor] = []

    for file_kind, filename in _CANONICAL_SESSION_FILES.items():
        path = session_path / filename
        if not path.exists():
            continue
        storage_metadata = read_storage_metadata(path)
        files.append(
            SessionFileDescriptor(
                file_kind=file_kind,
                path=str(path),
                schema_name=storage_metadata.schema_name if storage_metadata else None,
                format=storage_metadata.format if storage_metadata else None,
                signal_type=storage_metadata.signal_type if storage_metadata else None,
                metadata_json=(storage_metadata.model_dump_json() if storage_metadata else None),
            )
        )

    return SessionBundleDescriptor(
        session_dir=str(session_path),
        subject_id=_extract_identity_component(session_path, prefix="sub-"),
        session_id=_extract_identity_component(session_path, prefix="ses-"),
        files=files,
    )


def _extract_identity_component(path: Path, *, prefix: str) -> str | None:
    for part in path.parts:
        if part.startswith(prefix):
            return part
    return None
