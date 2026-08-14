"""MoveDB catalog — DuckDB interface for biomechanics data.

Provides convenient methods for querying motion capture data stored as Parquet files.
Uses patito for schema validation and DuckDB for SQL queries.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import polars as pl

from ..schemas import Markers, Forceplates, Events, Sessions

logger = logging.getLogger(__name__)


class MoveDB:
    """Domain-specific interface for biomechanics data.

    Registers Parquet files as DuckDB tables and provides
    convenient methods for common queries.

    Example::

        from movedb import MoveDB

        db = MoveDB(Path("data/processed"))

        # Load with schema validation
        markers = db.get_markers("BAA01", "baseline")

        # SQL query across all subjects
        df = db.query("SELECT subject_id, AVG(mass) FROM sessions GROUP BY subject_id")
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.conn = duckdb.connect()
        self._register_tables()

    def _register_tables(self):
        """Register all Parquet files as DuckDB tables."""
        for subject_dir in sorted(self.data_dir.iterdir()):
            if not subject_dir.is_dir():
                continue

            for parquet in subject_dir.glob("*.parquet"):
                table_name = f"{subject_dir.name}_{parquet.stem}"
                try:
                    self.conn.execute(
                        f"CREATE OR REPLACE TABLE {table_name} "
                        f"AS SELECT * FROM read_parquet('{parquet}')"
                    )
                except Exception as e:
                    logger.warning(f"Failed to register {parquet}: {e}")

    def get_markers(self, subject_id: str, session: str | None = None) -> pl.DataFrame:
        """Load markers with schema validation.

        Parameters
        ----------
        subject_id : str
            Subject identifier (e.g., "BAA01").
        session : str or None
            Session name (e.g., "baseline"). If None, returns all sessions.

        Returns
        -------
        pl.DataFrame
            Validated markers DataFrame.
        """
        path = self.data_dir / subject_id / "markers.parquet"
        df = pl.read_parquet(path)
        if session:
            df = df.filter(pl.col("session_id") == session)
        Markers.validate(df)
        return df

    def get_forceplates(self, subject_id: str, session: str | None = None) -> pl.DataFrame:
        """Load force plates with schema validation."""
        path = self.data_dir / subject_id / "forceplates.parquet"
        df = pl.read_parquet(path)
        if session:
            df = df.filter(pl.col("session_id") == session)
        Forceplates.validate(df)
        return df

    def get_events(self, subject_id: str, session: str | None = None) -> pl.DataFrame:
        """Load events with schema validation."""
        path = self.data_dir / subject_id / "events.parquet"
        df = pl.read_parquet(path)
        if session:
            df = df.filter(pl.col("session_id") == session)
        Events.validate(df)
        return df

    def get_sessions(self, subject_id: str | None = None) -> pl.DataFrame:
        """Load session parameters with schema validation."""
        if subject_id:
            path = self.data_dir / subject_id / "sessions.parquet"
            df = pl.read_parquet(path)
        else:
            # Load all subjects
            dfs = []
            for subject_dir in sorted(self.data_dir.iterdir()):
                if subject_dir.is_dir():
                    sessions_path = subject_dir / "sessions.parquet"
                    if sessions_path.exists():
                        dfs.append(pl.read_parquet(sessions_path))
            df = pl.concat(dfs, how="diagonal") if dfs else pl.DataFrame()

        Sessions.validate(df)
        return df

    def query(self, sql: str) -> pl.DataFrame:
        """Execute SQL query across all registered data.

        Parameters
        ----------
        sql : str
            SQL query to execute.

        Returns
        -------
        pl.DataFrame
            Query results.
        """
        return self.conn.execute(sql).pl()

    def subjects(self) -> list[str]:
        """List available subjects."""
        return sorted([
            d.name for d in self.data_dir.iterdir()
            if d.is_dir() and (d / "markers.parquet").exists()
        ])

    def sessions(self, subject_id: str) -> list[str]:
        """List available sessions for a subject."""
        sessions_path = self.data_dir / subject_id / "sessions.parquet"
        if not sessions_path.exists():
            return []
        df = pl.read_parquet(sessions_path)
        return sorted(df["session_id"].unique().to_list())
