"""DuckDB connection helpers for MoveDB catalogs and bundles."""

from __future__ import annotations

from pathlib import Path

from duckdb import connect

from .protocols import CatalogConnection
from .registry import initialize_catalog
from .views import create_bundle_views


def connect_catalog(
    path: str | Path | None = None,
    *,
    read_only: bool = False,
) -> CatalogConnection:
    """Open a persistent catalog database and initialize base tables."""

    database = str(path) if path is not None else ":memory:"
    conn = connect(database=database, read_only=read_only)
    if not read_only:
        initialize_catalog(conn)
    return conn


def open_bundle(session_dir: str | Path) -> CatalogConnection:
    """Open an in-memory DuckDB connection with session-local bundle views."""

    conn = connect(database=":memory:")
    create_bundle_views(conn, session_dir)
    return conn
