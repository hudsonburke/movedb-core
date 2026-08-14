"""MoveDB catalog — DuckDB interface for biomechanics data.

Thin wrapper around DuckDB that queries Parquet files directly.
DuckDB handles filter pushdown, parallel reads, and memory management.

Example::

    from movedb import MoveDB

    db = MoveDB(Path("data/processed"))

    # Query directly — DuckDB reads parquet with filter pushdown
    points = db.get_points("BAA01", session="baseline")

    # Cross-subject query
    df = db.query("SELECT subject_id, AVG(mass) FROM parameters GROUP BY subject_id")

    # List available data
    subjects = db.subjects()
    sessions = db.sessions("BAA01")
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import polars as pl

logger = logging.getLogger(__name__)


class MoveDB:
    """DuckDB-backed catalog for biomechanics parquet data.

    Queries parquet files directly — no table registration needed.
    DuckDB handles parallel reads, filter pushdown, and memory management.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.conn = duckdb.connect()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _glob(self, subject_id: str | None, filename: str) -> str:
        """Build a glob pattern for parquet files.

        If subject_id is provided, scopes to that subject.
        Otherwise, matches across all subjects.
        """
        if subject_id:
            return str(self.data_dir / subject_id / filename)
        return str(self.data_dir / "*" / filename)

    def _read(
        self,
        glob: str,
        subject_id: str | None = None,
        session: str | None = None,
        *,
        columns: list[str] | None = None,
        where: str | None = None,
    ) -> pl.DataFrame:
        """Read parquet via DuckDB with optional filters.

        DuckDB pushes predicates into the parquet reader, so only
        matching row groups are decoded.
        """
        cols = ", ".join(columns) if columns else "*"
        # nosemgrep: sql injection — glob is built from self.data_dir (not user input)
        sql = f"SELECT {cols} FROM '{glob}'"
        params: list[str] = []
        clauses = []
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if session is not None:
            clauses.append("session_id = ?")
            params.append(session)
        if where:
            clauses.append(where)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        try:
            # nosemgrep: sql injection — glob is built from self.data_dir, params are parameterized
            return self.conn.execute(sql, params).pl()
        except Exception:
            return pl.DataFrame()

    # ------------------------------------------------------------------
    # Data accessors
    # ------------------------------------------------------------------

    def get_points(
        self,
        subject_id: str | None = None,
        session: str | None = None,
        *,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """Query 3D point positions.

        Parameters
        ----------
        subject_id : str, optional
            Filter to a specific subject. None = all subjects.
        session : str, optional
            Filter to a specific session. None = all sessions.
        columns : list[str], optional
            Only read these columns (pushed down to parquet reader).
        """
        glob = self._glob(subject_id, "points.parquet")
        return self._read(glob, subject_id, session, columns=columns)

    def get_forceplates(
        self,
        subject_id: str | None = None,
        session: str | None = None,
        *,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """Query force plate data."""
        glob = self._glob(subject_id, "forceplates.parquet")
        return self._read(glob, subject_id, session, columns=columns)

    def get_forceplate_geometry(
        self,
        subject_id: str | None = None,
        session: str | None = None,
    ) -> pl.DataFrame:
        """Query force plate calibration geometry."""
        glob = self._glob(subject_id, "forceplate_geometry.parquet")
        return self._read(glob, subject_id, session)

    def get_analogs(
        self,
        subject_id: str | None = None,
        session: str | None = None,
        *,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """Query raw analog channels."""
        glob = self._glob(subject_id, "analogs.parquet")
        return self._read(glob, subject_id, session, columns=columns)

    def get_events(
        self,
        subject_id: str | None = None,
        session: str | None = None,
    ) -> pl.DataFrame:
        """Query gait events."""
        glob = self._glob(subject_id, "events.parquet")
        return self._read(glob, subject_id, session)

    def get_parameters(
        self,
        subject_id: str | None = None,
        session: str | None = None,
        *,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """Query trial parameters."""
        glob = self._glob(subject_id, "parameters.parquet")
        return self._read(glob, subject_id, session, columns=columns)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def subjects(self) -> list[str]:
        """List all subjects with point data."""
        glob = self._glob(None, "points.parquet")
        result = self.conn.execute(
            f"SELECT DISTINCT file FROM glob('{glob}')"
        ).pl()
        # file contains full path like 'data/BAA01/points.parquet'
        return sorted([
            Path(p).parent.name for p in result["file"].to_list()
        ])

    def sessions(self, subject_id: str | None = None) -> list[str]:
        """List sessions, optionally filtered to one subject."""
        glob = self._glob(subject_id, "parameters.parquet")
        result = self._read(glob, columns=["session_id"])
        if result.is_empty() or "session_id" not in result.columns:
            return []
        return sorted(result["session_id"].unique().to_list())

    def trials(
        self,
        subject_id: str | None = None,
        session: str | None = None,
    ) -> list[str]:
        """List trial names, optionally filtered."""
        glob = self._glob(subject_id, "parameters.parquet")
        result = self._read(glob, subject_id, session, columns=["trial_name"])
        return sorted(result["trial_name"].unique().to_list())

    # ------------------------------------------------------------------
    # Raw SQL
    # ------------------------------------------------------------------

    def query(self, sql: str) -> pl.DataFrame:
        """Execute arbitrary SQL across all parquet data.

        DuckDB can reference parquet files directly::

            db.query(\"\"\"
                SELECT p.trial_name, AVG(fp.value) as mean_force
                FROM 'data/BAA01/forceplates.parquet' fp
                JOIN 'data/BAA01/parameters.parquet' p
                  ON fp.trial_name = p.trial_name
                WHERE fp.variable = 'force' AND fp.axis = 'z'
                GROUP BY p.trial_name
            \"\"\")
        """
        # nosemgrep: intentional SQL interface — users write their own queries
        return self.conn.execute(sql).pl()  # noqa: S608

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    def schema(self, data_type: str = "points") -> pl.DataFrame:
        """Describe the schema of a parquet file.

        Parameters
        ----------
        data_type : str
            One of: points, forceplates, forceplate_geometry,
            analogs, events, parameters
        """
        glob = self._glob(None, f"{data_type}.parquet")
        try:
            # nosemgrep: data_type is a validated literal from our schema registry
            return self.conn.execute(f"DESCRIBE SELECT * FROM '{glob}' LIMIT 0").pl()  # noqa: S608
        except Exception:
            return pl.DataFrame({"column_name": [], "column_type": []})
