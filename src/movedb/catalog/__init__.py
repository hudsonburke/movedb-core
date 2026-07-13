"""DuckDB-backed catalog layer for cross-session discovery and queries."""

from .discovery import SessionBundleDescriptor, SessionFileDescriptor, discover_session_bundle
from .duckdb import connect_catalog, open_bundle
from .metrics import refresh_selection_metrics
from .notebook import (
    connect_workbench_catalog,
    register_scratch_views,
    sql_compare_canonical_vs_scratch,
    sql_current_view_preview,
    sql_list_sessions,
    sql_list_subjects,
    sql_list_trials,
)
from .quality import write_session_quality, write_trial_quality
from .registry import (
    initialize_catalog,
    refresh_catalog,
    register_dataset_root,
    register_session_bundle,
    register_session_bundles,
)
from .views import create_bundle_views, create_catalog_views

__all__ = [
    "SessionBundleDescriptor",
    "SessionFileDescriptor",
    "connect_catalog",
    "connect_workbench_catalog",
    "create_bundle_views",
    "create_catalog_views",
    "discover_session_bundle",
    "initialize_catalog",
    "open_bundle",
    "register_scratch_views",
    "refresh_selection_metrics",
    "refresh_catalog",
    "register_dataset_root",
    "register_session_bundle",
    "register_session_bundles",
    "sql_compare_canonical_vs_scratch",
    "sql_current_view_preview",
    "sql_list_sessions",
    "sql_list_subjects",
    "sql_list_trials",
    "write_session_quality",
    "write_trial_quality",
]
