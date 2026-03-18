"""Registration helpers for DuckDB catalog tables."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import duckdb

from .discovery import SessionBundleDescriptor, discover_session_bundle
from .sql import CATALOG_SCHEMA_SQL, CREATE_SESSION_FILES_TABLE_SQL, CREATE_SESSIONS_TABLE_SQL
from .views import create_catalog_views


def initialize_catalog(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the base catalog schema and registry tables."""

    conn.execute(CATALOG_SCHEMA_SQL)
    conn.execute(CREATE_SESSIONS_TABLE_SQL)
    conn.execute(CREATE_SESSION_FILES_TABLE_SQL)


def register_session_bundle(conn: duckdb.DuckDBPyConnection, session_dir: str | Path) -> SessionBundleDescriptor:
    """Discover and register one session bundle into the catalog."""

    descriptor = discover_session_bundle(session_dir)
    _upsert_session(conn, descriptor)
    _upsert_session_files(conn, descriptor)
    create_catalog_views(conn)
    return descriptor


def register_session_bundles(
    conn: duckdb.DuckDBPyConnection,
    session_dirs: Iterable[str | Path],
) -> list[SessionBundleDescriptor]:
    """Register multiple session bundles into the catalog."""

    descriptors = [register_session_bundle(conn, session_dir) for session_dir in session_dirs]
    create_catalog_views(conn)
    return descriptors


def refresh_catalog(conn: duckdb.DuckDBPyConnection) -> None:
    """Refresh derived catalog views after registration changes."""

    create_catalog_views(conn)


def _upsert_session(conn: duckdb.DuckDBPyConnection, descriptor: SessionBundleDescriptor) -> None:
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


def _upsert_session_files(conn: duckdb.DuckDBPyConnection, descriptor: SessionBundleDescriptor) -> None:
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
