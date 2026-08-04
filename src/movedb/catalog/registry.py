"""Registration helpers for DuckDB catalog tables."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .discovery import SessionBundleDescriptor, discover_session_bundle
from .protocols import CatalogConnection
from .sql import (
    CREATE_CATALOG_SETTINGS_TABLE_SQL,
    CATALOG_SCHEMA_SQL,
    CREATE_OSIM_ARTIFACTS_TABLE_SQL,
    CREATE_SESSION_FILES_TABLE_SQL,
    CREATE_SESSION_METRICS_TABLE_SQL,
    CREATE_SESSIONS_TABLE_SQL,
    CREATE_SESSION_QUALITY_TABLE_SQL,
    CREATE_TRIAL_METRICS_TABLE_SQL,
    CREATE_TRIAL_QUALITY_TABLE_SQL,
)
from .views import create_catalog_views


def initialize_catalog(conn: CatalogConnection) -> None:
    """Create the base catalog schema and registry tables."""

    conn.execute(CATALOG_SCHEMA_SQL)
    conn.execute(CREATE_CATALOG_SETTINGS_TABLE_SQL)
    conn.execute(CREATE_SESSIONS_TABLE_SQL)
    conn.execute(CREATE_SESSION_FILES_TABLE_SQL)
    conn.execute(CREATE_SESSION_METRICS_TABLE_SQL)
    conn.execute(CREATE_TRIAL_METRICS_TABLE_SQL)
    conn.execute(CREATE_SESSION_QUALITY_TABLE_SQL)
    conn.execute(CREATE_TRIAL_QUALITY_TABLE_SQL)
    conn.execute(CREATE_OSIM_ARTIFACTS_TABLE_SQL)


def register_osim_artifact(conn: CatalogConnection, row: OsimArtifactRow) -> None:
    if row["is_canonical"]:
        conn.execute(
            """
            UPDATE movedb_catalog.osim_artifacts
            SET is_canonical = FALSE
            WHERE session_key = ?
              AND pipeline = ?
              AND scope = ?
              AND trial_key IS NOT DISTINCT FROM ?
            """,
            [row["session_key"], row["pipeline"], row["scope"], row["trial_key"]],
        )
    conn.execute(
        """
        INSERT OR REPLACE INTO movedb_catalog.osim_artifacts (
            artifact_id, run_id, pipeline, output_kind, scope,
            session_key, trial_key, path, native_path, format,
            status, is_canonical, created_at, parameter_hash,
            parameter_json, provenance_json, extras_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            row["artifact_id"],
            row["run_id"],
            row["pipeline"],
            row["output_kind"],
            row["scope"],
            row["session_key"],
            row["trial_key"],
            row["path"],
            row["native_path"],
            row["format"],
            row["status"],
            row["is_canonical"],
            row["created_at"],
            row["parameter_hash"],
            row["parameter_json"],
            row["provenance_json"],
            row["extras_json"],
        ],
    )


def register_osim_artifacts(conn: CatalogConnection, rows: list[OsimArtifactRow]) -> None:
    for row in rows:
        register_osim_artifact(conn, row)


def register_session_bundle(conn: CatalogConnection, session_dir: str | Path) -> SessionBundleDescriptor:
    """Discover and register one session bundle into the catalog."""

    descriptor = discover_session_bundle(session_dir)
    _upsert_session(conn, descriptor)
    _upsert_session_files(conn, descriptor)
    create_catalog_views(conn)
    return descriptor


def register_session_bundles(
    conn: CatalogConnection,
    session_dirs: Iterable[str | Path],
) -> list[SessionBundleDescriptor]:
    """Register multiple session bundles into the catalog."""

    descriptors = [register_session_bundle(conn, session_dir) for session_dir in session_dirs]
    create_catalog_views(conn)
    return descriptors


def register_dataset_root(
    conn: CatalogConnection,
    root: str | Path,
    *,
    pattern: str = "sub-*/ses-*/motion",
) -> list[SessionBundleDescriptor]:
    """Discover and register all session bundles under a dataset root."""

    root = Path(root)
    conn.execute(
        """
        INSERT INTO movedb_catalog.catalog_settings (setting_key, setting_value)
        VALUES ('dataset_root', ?)
        ON CONFLICT (setting_key) DO UPDATE SET setting_value = excluded.setting_value
        """,
        [str(root.resolve())],
    )
    session_dirs = sorted(path for path in root.glob(pattern) if path.is_dir())
    return register_session_bundles(conn, session_dirs)


def refresh_catalog(conn: CatalogConnection) -> None:
    """Refresh derived catalog views after registration changes."""

    create_catalog_views(conn)


def _upsert_session(conn: CatalogConnection, descriptor: SessionBundleDescriptor) -> None:
    conn.execute(
        """
        INSERT INTO movedb_catalog.sessions (session_dir, subject_id, session_id)
        VALUES (?, ?, ?)
        ON CONFLICT (session_dir) DO UPDATE SET
            subject_id = excluded.subject_id,
            session_id = excluded.session_id
        """,
        [descriptor.session_dir, descriptor.subject_id, descriptor.session_id],
    )


def _upsert_session_files(conn: CatalogConnection, descriptor: SessionBundleDescriptor) -> None:
    for file in descriptor.files:
        conn.execute(
            """
            INSERT INTO movedb_catalog.session_files (
                session_dir,
                file_kind,
                path,
                schema_name,
                format,
                signal_type,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (session_dir, file_kind) DO UPDATE SET
                path = excluded.path,
                schema_name = excluded.schema_name,
                format = excluded.format,
                signal_type = excluded.signal_type,
                metadata_json = excluded.metadata_json
            """,
            [
                descriptor.session_dir,
                file.file_kind,
                file.path,
                file.schema_name,
                file.format,
                file.signal_type,
                file.metadata_json,
            ],
        )
