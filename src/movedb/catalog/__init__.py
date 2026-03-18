"""DuckDB-backed catalog layer for cross-session discovery and queries."""

from .discovery import SessionBundleDescriptor, SessionFileDescriptor, discover_session_bundle
from .duckdb import connect_catalog, open_bundle
from .registry import initialize_catalog, refresh_catalog, register_session_bundle, register_session_bundles
from .views import create_bundle_views, create_catalog_views

__all__ = [
    "SessionBundleDescriptor",
    "SessionFileDescriptor",
    "connect_catalog",
    "create_bundle_views",
    "create_catalog_views",
    "discover_session_bundle",
    "initialize_catalog",
    "open_bundle",
    "refresh_catalog",
    "register_session_bundle",
    "register_session_bundles",
]
