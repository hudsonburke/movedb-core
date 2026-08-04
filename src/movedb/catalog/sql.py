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

CREATE_CATALOG_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movedb_catalog.catalog_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT
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

CREATE_SESSION_METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movedb_catalog.session_metrics (
    session_key TEXT PRIMARY KEY,
    subject_id TEXT,
    session_id TEXT,
    motion_dir TEXT,
    metrics_version TEXT,
    source_signature TEXT,
    has_scaling_parameters BOOLEAN,
    missing_scaling_parameters_json TEXT,
    static_trial TEXT,
    has_static_trial BOOLEAN,
    static_missing_markers_json TEXT,
    static_has_required_markers BOOLEAN,
    static_has_scaling_window BOOLEAN,
    static_valid_frames BIGINT,
    static_valid_frames_relaxed BIGINT,
    static_rate_hz DOUBLE,
    static_min_frames BIGINT,
    qualifies_for_osim BOOLEAN,
    reason TEXT,
    mass_kg DOUBLE,
    right_femur_length_mm DOUBLE,
    left_femur_length_mm DOUBLE,
    right_tibia_length_mm DOUBLE,
    left_tibia_length_mm DOUBLE,
    right_foot_length_mm DOUBLE,
    left_foot_length_mm DOUBLE,
    parameter_flags_json TEXT
);
"""

CREATE_TRIAL_METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movedb_catalog.trial_metrics (
    trial_key TEXT PRIMARY KEY,
    session_key TEXT,
    subject_id TEXT,
    session_id TEXT,
    trial_name TEXT,
    motion_dir TEXT,
    metrics_version TEXT,
    source_signature TEXT,
    is_static BOOLEAN,
    is_walk_candidate BOOLEAN,
    event_count BIGINT,
    event_sequence_valid BOOLEAN,
    event_sequence_json TEXT,
    t_start DOUBLE,
    t_end DOUBLE,
    gait_duration_s DOUBLE,
    marker_gaps_present BOOLEAN,
    missing_markers_json TEXT,
    has_enf_trial BOOLEAN,
    has_fp_mapping BOOLEAN,
    fp_mapping_json TEXT,
    enf_notes TEXT,
    qualifies_for_ik BOOLEAN,
    qualifies_for_id BOOLEAN,
    reason TEXT
);
"""

CREATE_SESSION_QUALITY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movedb_catalog.session_quality (
    session_key TEXT PRIMARY KEY,
    session_dir TEXT NOT NULL,
    subject_id TEXT,
    session_id TEXT,
    qualifies_for_osim BOOLEAN NOT NULL,
    static_trial TEXT,
    reason TEXT,
    motion_dir TEXT,
    opensim_dir TEXT,
    mass_kg DOUBLE,
    right_femur_length_mm DOUBLE,
    left_femur_length_mm DOUBLE,
    right_tibia_length_mm DOUBLE,
    left_tibia_length_mm DOUBLE,
    right_foot_length_mm DOUBLE,
    left_foot_length_mm DOUBLE,
    metadata_json TEXT
);
"""

CREATE_TRIAL_QUALITY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movedb_catalog.trial_quality (
    trial_key TEXT PRIMARY KEY,
    session_key TEXT NOT NULL,
    subject_id TEXT,
    session_id TEXT,
    trial_name TEXT NOT NULL,
    qualifies_for_ik BOOLEAN NOT NULL,
    qualifies_for_id BOOLEAN NOT NULL,
    reason TEXT,
    t_start DOUBLE,
    t_end DOUBLE,
    motion_dir TEXT,
    opensim_dir TEXT,
    has_fp_mapping BOOLEAN,
    fp_mapping TEXT,
    enf_notes TEXT,
    metadata_json TEXT
);
"""

SESSION_INVENTORY_VIEW_SQL = """
CREATE OR REPLACE VIEW movedb_catalog.session_inventory AS
SELECT
    s.session_dir,
    s.subject_id,
    s.session_id,
    MAX(CASE WHEN f.file_kind = 'markers' THEN 1 ELSE 0 END) AS has_markers,
    MAX(CASE WHEN f.file_kind = 'analogs' THEN 1 ELSE 0 END) AS has_analogs,
    MAX(CASE WHEN f.file_kind = 'forceplates' THEN 1 ELSE 0 END) AS has_forceplates,
    MAX(CASE WHEN f.file_kind = 'events' THEN 1 ELSE 0 END) AS has_events,
    MAX(CASE WHEN f.file_kind = 'parameters' THEN 1 ELSE 0 END) AS has_parameters,
    COUNT(f.file_kind) AS file_count
FROM movedb_catalog.sessions AS s
LEFT JOIN movedb_catalog.session_files AS f
    ON s.session_dir = f.session_dir
GROUP BY s.session_dir, s.subject_id, s.session_id;
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

TRIAL_MANIFEST_VIEW_SQL = """
CREATE OR REPLACE VIEW movedb_catalog.trial_manifest AS
WITH event_summary AS (
    SELECT
        subject_id,
        session_id,
        trial_name,
        COUNT(*) AS event_count,
        MIN(time) AS t_start,
        MAX(time) AS t_end
    FROM movedb_catalog.events
    WHERE trial_name IS NOT NULL
    GROUP BY subject_id, session_id, trial_name
),
trial_files AS (
    SELECT
        s.subject_id,
        s.session_id,
        s.session_dir,
        MAX(CASE WHEN f.file_kind = 'markers' THEN 1 ELSE 0 END) AS has_markers,
        MAX(CASE WHEN f.file_kind = 'forceplates' THEN 1 ELSE 0 END) AS has_forceplates,
        MAX(CASE WHEN f.file_kind = 'events' THEN 1 ELSE 0 END) AS has_events,
        MAX(CASE WHEN f.file_kind = 'parameters' THEN 1 ELSE 0 END) AS has_parameters
    FROM movedb_catalog.sessions AS s
    LEFT JOIN movedb_catalog.session_files AS f
        ON s.session_dir = f.session_dir
    GROUP BY s.subject_id, s.session_id, s.session_dir
)
SELECT
    e.subject_id,
    e.session_id,
    tf.session_dir,
    e.trial_name,
    e.event_count,
    e.t_start,
    e.t_end,
    tf.has_markers,
    tf.has_forceplates,
    tf.has_events,
    tf.has_parameters
FROM event_summary AS e
LEFT JOIN trial_files AS tf
    ON e.subject_id = tf.subject_id
    AND e.session_id = tf.session_id;
"""

SESSION_SELECTION_METRICS_VIEW_SQL = """
CREATE OR REPLACE VIEW movedb_catalog.session_selection_metrics AS
SELECT *
FROM movedb_catalog.session_metrics;
"""

TRIAL_SELECTION_METRICS_VIEW_SQL = """
CREATE OR REPLACE VIEW movedb_catalog.trial_selection_metrics AS
SELECT *
FROM movedb_catalog.trial_metrics;
"""

OSIM_SESSIONS_VIEW_SQL = """
"""

QUALIFIED_TRIALS_VIEW_SQL = """
CREATE OR REPLACE VIEW movedb_catalog.qualified_trials AS
SELECT *
FROM movedb_catalog.trial_quality
WHERE qualifies_for_ik = TRUE;
"""

ID_TRIALS_VIEW_SQL = """
CREATE OR REPLACE VIEW movedb_catalog.id_trials AS
SELECT *
FROM movedb_catalog.trial_quality
WHERE qualifies_for_id = TRUE;
"""

CREATE_OSIM_ARTIFACTS_TABLE_SQL = """
"""

OSIM_ARTIFACTS_VIEW_SQL = """
"""

OSIM_IK_VIEW_SQL = """
"""

OSIM_ID_VIEW_SQL = """
"""

LATEST_OSIM_IK_VIEW_SQL = """
"""

LATEST_OSIM_ID_VIEW_SQL = """
"""
