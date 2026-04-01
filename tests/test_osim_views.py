"""Tests for DuckDB views over osim_artifacts table (TDD)."""

from __future__ import annotations

import duckdb
import pytest

from movedb.catalog.registry import initialize_catalog, register_osim_artifact
from movedb.catalog.views import create_catalog_views
from movedb.osim.types import make_artifact_id


def _make_row(
    *,
    pipeline: str,
    session_key: str,
    trial_key: str,
    created_at: str,
    run_id: str | None = None,
    is_canonical: bool = False,
    output_kind: str | None = None,
) -> dict:
    if run_id is None:
        run_id = make_artifact_id().replace("-", "").ljust(64, "0")[:64]
    if output_kind is None:
        output_kind = f"{pipeline}_positions"
    return {
        "artifact_id": make_artifact_id(),
        "run_id": run_id,
        "pipeline": pipeline,
        "output_kind": output_kind,
        "scope": "trial",
        "session_key": session_key,
        "trial_key": trial_key,
        "path": f"runs/{run_id[:12]}/{trial_key}_{pipeline}.parquet",
        "native_path": None,
        "format": "parquet",
        "status": "complete",
        "is_canonical": is_canonical,
        "created_at": created_at,
        "parameter_hash": "x" * 64,
        "parameter_json": "{}",
        "provenance_json": None,
        "extras_json": None,
    }


@pytest.fixture
def conn_with_fixtures():
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    sessions = ["s1", "s2"]
    trials = ["t1", "t2"]
    dates = ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"]

    for session in sessions:
        for trial in trials:
            for i, ts in enumerate(dates):
                register_osim_artifact(
                    conn,
                    _make_row(
                        pipeline="ik",
                        session_key=session,
                        trial_key=trial,
                        created_at=ts,
                        is_canonical=(i == 1),
                    ),
                )

    register_osim_artifact(
        conn,
        _make_row(
            pipeline="id",
            session_key="s1",
            trial_key="t1",
            created_at="2026-01-01T00:00:00Z",
        ),
    )

    create_catalog_views(conn)
    return conn


def test_osim_artifacts_view_returns_all(conn_with_fixtures):
    """osim_artifacts_view returns all 9 rows (8 IK + 1 ID)."""
    count = conn_with_fixtures.execute(
        "SELECT COUNT(*) FROM movedb_catalog.osim_artifacts_view"
    ).fetchone()[0]
    assert count == 9, f"Expected 9, got {count}"


def test_osim_ik_view_filters_to_ik_only(conn_with_fixtures):
    """osim_ik view returns only IK artifacts (count = 8)."""
    count = conn_with_fixtures.execute(
        "SELECT COUNT(*) FROM movedb_catalog.osim_ik"
    ).fetchone()[0]
    assert count == 8, f"Expected 8, got {count}"

    pipelines = conn_with_fixtures.execute(
        "SELECT DISTINCT pipeline FROM movedb_catalog.osim_ik"
    ).fetchall()
    assert pipelines == [("ik",)], f"Expected only 'ik', got {pipelines}"


def test_osim_id_view_filters_to_id_only(conn_with_fixtures):
    """osim_id view returns only ID artifacts (count = 1)."""
    count = conn_with_fixtures.execute(
        "SELECT COUNT(*) FROM movedb_catalog.osim_id"
    ).fetchone()[0]
    assert count == 1, f"Expected 1, got {count}"

    pipelines = conn_with_fixtures.execute(
        "SELECT DISTINCT pipeline FROM movedb_catalog.osim_id"
    ).fetchall()
    assert pipelines == [("id",)], f"Expected only 'id', got {pipelines}"


def test_latest_osim_ik_returns_one_per_session_trial(conn_with_fixtures):
    """latest_osim_ik returns 4 rows — one per session+trial combination."""
    count = conn_with_fixtures.execute(
        "SELECT COUNT(*) FROM movedb_catalog.latest_osim_ik"
    ).fetchone()[0]
    assert count == 4, f"Expected 4 (1 per session×trial), got {count}"


def test_latest_osim_ik_returns_most_recent_created_at(conn_with_fixtures):
    """latest_osim_ik selects the run with the latest created_at for each session+trial."""
    rows = conn_with_fixtures.execute(
        "SELECT created_at FROM movedb_catalog.latest_osim_ik ORDER BY created_at"
    ).fetchall()
    for row in rows:
        assert row[0] == "2026-01-02T00:00:00Z", (
            f"Expected '2026-01-02T00:00:00Z', got '{row[0]}'"
        )


def test_latest_osim_id_returns_one_row(conn_with_fixtures):
    """latest_osim_id returns 1 row for the single ID artifact."""
    count = conn_with_fixtures.execute(
        "SELECT COUNT(*) FROM movedb_catalog.latest_osim_id"
    ).fetchone()[0]
    assert count == 1, f"Expected 1, got {count}"


def test_latest_osim_ik_tiebreaker_by_run_id():
    """When created_at ties, latest_osim_ik picks the lexicographically larger run_id."""
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    ts = "2026-06-01T00:00:00Z"
    run_id_smaller = "a" * 64
    run_id_larger = "b" * 64

    register_osim_artifact(
        conn,
        _make_row(
            pipeline="ik",
            session_key="sx",
            trial_key="tx",
            created_at=ts,
            run_id=run_id_smaller,
        ),
    )
    register_osim_artifact(
        conn,
        _make_row(
            pipeline="ik",
            session_key="sx",
            trial_key="tx",
            created_at=ts,
            run_id=run_id_larger,
        ),
    )

    create_catalog_views(conn)

    rows = conn.execute(
        "SELECT run_id FROM movedb_catalog.latest_osim_ik"
    ).fetchall()

    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    assert rows[0][0] == run_id_larger, (
        f"Expected larger run_id '{run_id_larger}', got '{rows[0][0]}'"
    )
