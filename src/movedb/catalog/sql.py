"""Central SQL snippets for the DuckDB catalog layer."""

from __future__ import annotations

CATALOG_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS movedb_catalog;"

CREATE_SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movedb_catalog.sessions (
    session_dir TEXT PRIMARY KEY,
    subject_id TEXT,
    session_id TEXT
);
"""

CREATE_SESSION_FILES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movedb_catalog.session_files (
    session_dir TEXT NOT NULL,
    file_kind TEXT NOT NULL,
    path TEXT NOT NULL,
    schema_name TEXT,
    format TEXT,
    signal_type TEXT,
    metadata_json TEXT,
    PRIMARY KEY (session_dir, file_kind)
);
"""

TRIALS_VIEW_SQL = """
CREATE OR REPLACE VIEW movedb_catalog.trials AS
SELECT DISTINCT
    subject_id,
    session_id,
    trial_name
FROM movedb_catalog.events
WHERE trial_name IS NOT NULL;
"""
