"""MoveDB catalog — DuckDB interface for biomechanics data.

Provides convenient methods for querying motion capture data stored as Parquet files.
Uses patito for schema validation and DuckDB for SQL queries.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import polars as pl

from ..schemas import Points, Forceplates, ForceplateGeometry, Analogs, Events, Parameters

logger = logging.getLogger(__name__)


class MoveDB:
    """Domain-specific interface for biomechanics data.

    Registers Parquet files as DuckDB tables and provides
    convenient methods for common queries.

    Example::

        from movedb import MoveDB

        db = MoveDB(Path("data/processed"))

        # Load with schema validation
        points = db.get_points("BAA01", "baseline")

        # SQL query across all subjects
        df = db.query("SELECT subject_id, AVG(mass) FROM parameters GROUP BY subject_id")
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.conn = duckdb.connect()
        self._register_tables()

    def _register_tables(self):
        """Register all Parquet files as DuckDB tables."""
        import re

        for subject_dir in sorted(self.data_dir.iterdir()):
            if not subject_dir.is_dir():
                continue

            for parquet in subject_dir.glob("*.parquet"):
                # Sanitize table name to valid identifier
                table_name = f"{subject_dir.name}_{parquet.stem}"
                table_name = re.sub(r"[^a-zA-Z0-9_]", "_", table_name)
                try:
                    self.conn.execute(
                        "CREATE OR REPLACE TABLE "
                        f"{table_name} AS SELECT * FROM read_parquet(?)",
                        [str(parquet)],
                    )
                except Exception as e:
                    logger.warning(f"Failed to register {parquet}: {e}")

    def get_points(self, subject_id: str, session: str | None = None) -> pl.DataFrame:
        """Load 3D point positions with schema validation.

        Parameters
        ----------
        subject_id : str
            Subject identifier (e.g., "BAA01").
        session : str or None
            Session name (e.g., "baseline"). If None, returns all sessions.

        Returns
        -------
        pl.DataFrame
            Validated points DataFrame.
        """
        path = self.data_dir / subject_id / "points.parquet"
        df = pl.read_parquet(path)
        if session:
            df = df.filter(pl.col("session_id") == session)
        Points.validate(df)
        return df

    def get_forceplates(self, subject_id: str, session: str | None = None) -> pl.DataFrame:
        """Load force plates with schema validation."""
        path = self.data_dir / subject_id / "forceplates.parquet"
        df = pl.read_parquet(path)
        if session:
            df = df.filter(pl.col("session_id") == session)
        Forceplates.validate(df)
        return df

    def get_forceplate_geometry(self, subject_id: str, session: str | None = None) -> pl.DataFrame:
        """Load force plate calibration with schema validation."""
        path = self.data_dir / subject_id / "forceplate_geometry.parquet"
        df = pl.read_parquet(path)
        if session:
            df = df.filter(pl.col("session_id") == session)
        ForceplateGeometry.validate(df)
        return df

    def get_analogs(self, subject_id: str, session: str | None = None) -> pl.DataFrame:
        """Load raw analog channels with schema validation."""
        path = self.data_dir / subject_id / "analogs.parquet"
        df = pl.read_parquet(path)
        if session:
            df = df.filter(pl.col("session_id") == session)
        Analogs.validate(df)
        return df

    def get_events(self, subject_id: str, session: str | None = None) -> pl.DataFrame:
        """Load events with schema validation."""
        path = self.data_dir / subject_id / "events.parquet"
        df = pl.read_parquet(path)
        if session:
            df = df.filter(pl.col("session_id") == session)
        Events.validate(df)
        return df

    def get_parameters(self, subject_id: str | None = None) -> pl.DataFrame:
        """Load trial parameters with schema validation."""
        if subject_id:
            path = self.data_dir / subject_id / "parameters.parquet"
            df = pl.read_parquet(path)
        else:
            # Load all subjects
            dfs = []
            for subject_dir in sorted(self.data_dir.iterdir()):
                if subject_dir.is_dir():
                    params_path = subject_dir / "parameters.parquet"
                    if params_path.exists():
                        dfs.append(pl.read_parquet(params_path))
            df = pl.concat(dfs, how="diagonal") if dfs else pl.DataFrame()

        Parameters.validate(df, allow_superfluous_columns=True)
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
            if d.is_dir() and (d / "points.parquet").exists()
        ])

    def sessions(self, subject_id: str) -> list[str]:
        """List available sessions for a subject."""
        params_path = self.data_dir / subject_id / "parameters.parquet"
        if not params_path.exists():
            return []
        df = pl.read_parquet(params_path)
        return sorted(df["session_id"].unique().to_list())
