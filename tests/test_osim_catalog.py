from __future__ import annotations

import duckdb

from movedb.catalog.registry import initialize_catalog, register_osim_artifact, register_osim_artifacts
from movedb.osim.types import make_artifact_id


def make_test_row(
    *,
    artifact_id: str | None = None,
    run_id: str = "a" * 64,
    pipeline: str = "ik",
    output_kind: str = "ik_positions",
    scope: str = "trial",
    session_key: str = "s1",
    trial_key: str | None = "t1",
    path: str = "out.parquet",
    native_path: str | None = None,
    format: str = "parquet",
    status: str = "complete",
    is_canonical: bool = False,
    created_at: str = "2026-01-01T00:00:00Z",
    parameter_hash: str = "p" * 64,
    parameter_json: str = "{}",
    provenance_json: str | None = None,
    extras_json: str | None = None,
) -> dict:
    return {
        "artifact_id": artifact_id if artifact_id is not None else make_artifact_id(),
        "run_id": run_id,
        "pipeline": pipeline,
        "output_kind": output_kind,
        "scope": scope,
        "session_key": session_key,
        "trial_key": trial_key,
        "path": path,
        "native_path": native_path,
        "format": format,
        "status": status,
        "is_canonical": is_canonical,
        "created_at": created_at,
        "parameter_hash": parameter_hash,
        "parameter_json": parameter_json,
        "provenance_json": provenance_json,
        "extras_json": extras_json,
    }


def test_initialize_catalog_creates_osim_artifacts_table() -> None:
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    columns = conn.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'movedb_catalog'
          AND table_name = 'osim_artifacts'
        ORDER BY ordinal_position
        """
    ).fetchall()

    column_names = [row[0] for row in columns]
    expected_columns = [
        "artifact_id",
        "run_id",
        "pipeline",
        "output_kind",
        "scope",
        "session_key",
        "trial_key",
        "path",
        "native_path",
        "format",
        "status",
        "is_canonical",
        "created_at",
        "parameter_hash",
        "parameter_json",
        "provenance_json",
        "extras_json",
    ]
    assert column_names == expected_columns, f"Column mismatch: {column_names}"

    col_map = {row[0]: row[1] for row in columns}
    assert col_map["artifact_id"] == "VARCHAR"
    assert col_map["is_canonical"] == "BOOLEAN"
    assert col_map["run_id"] == "VARCHAR"


def test_register_single_artifact() -> None:
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    row = make_test_row(
        artifact_id="art-001",
        pipeline="ik",
        status="complete",
        is_canonical=False,
    )
    register_osim_artifact(conn, row)

    rows = conn.execute("SELECT * FROM movedb_catalog.osim_artifacts").fetchall()
    assert len(rows) == 1

    result = rows[0]
    cols = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='movedb_catalog' AND table_name='osim_artifacts' "
        "ORDER BY ordinal_position"
    ).fetchall()
    col_names = [c[0] for c in cols]
    result_dict = dict(zip(col_names, result))

    assert result_dict["artifact_id"] == "art-001"
    assert result_dict["pipeline"] == "ik"
    assert result_dict["status"] == "complete"
    assert result_dict["is_canonical"] is False
    assert result_dict["session_key"] == "s1"
    assert result_dict["trial_key"] == "t1"


def test_upsert_same_artifact_id_updates_status() -> None:
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    artifact_id = make_artifact_id()

    row1 = make_test_row(artifact_id=artifact_id, status="running")
    register_osim_artifact(conn, row1)

    row2 = make_test_row(artifact_id=artifact_id, status="complete")
    register_osim_artifact(conn, row2)

    rows = conn.execute("SELECT artifact_id, status FROM movedb_catalog.osim_artifacts").fetchall()
    assert len(rows) == 1, f"Expected 1 row after upsert, got {len(rows)}"
    assert rows[0][1] == "complete", f"Expected status 'complete', got {rows[0][1]}"


def test_canonical_uniqueness_enforced() -> None:
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    id_a = make_artifact_id()
    id_b = make_artifact_id()

    row_a = make_test_row(
        artifact_id=id_a,
        session_key="s1",
        pipeline="ik",
        scope="trial",
        trial_key="t1",
        is_canonical=True,
        created_at="2026-01-01T00:00:00Z",
    )
    register_osim_artifact(conn, row_a)

    row_b = make_test_row(
        artifact_id=id_b,
        session_key="s1",
        pipeline="ik",
        scope="trial",
        trial_key="t1",
        is_canonical=True,
        created_at="2026-01-02T00:00:00Z",
    )
    register_osim_artifact(conn, row_b)

    rows = conn.execute(
        "SELECT artifact_id, is_canonical FROM movedb_catalog.osim_artifacts ORDER BY created_at"
    ).fetchall()

    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
    assert rows[0][0] == id_a
    assert rows[0][1] is False, "First artifact should no longer be canonical"
    assert rows[1][0] == id_b
    assert rows[1][1] is True, "Second artifact should be canonical"


def test_query_by_pipeline() -> None:
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    rows = [
        make_test_row(pipeline="ik", trial_key="t1"),
        make_test_row(pipeline="ik", trial_key="t2"),
        make_test_row(pipeline="id", trial_key="t3"),
    ]
    register_osim_artifacts(conn, rows)

    ik_rows = conn.execute(
        "SELECT * FROM movedb_catalog.osim_artifacts WHERE pipeline = 'ik'"
    ).fetchall()
    assert len(ik_rows) == 2, f"Expected 2 ik rows, got {len(ik_rows)}"

    id_rows = conn.execute(
        "SELECT * FROM movedb_catalog.osim_artifacts WHERE pipeline = 'id'"
    ).fetchall()
    assert len(id_rows) == 1, f"Expected 1 id row, got {len(id_rows)}"


def test_session_scoped_artifact_trial_key_is_null() -> None:
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    artifact_id = make_artifact_id()
    row = make_test_row(
        artifact_id=artifact_id,
        scope="session",
        trial_key=None,
    )
    register_osim_artifact(conn, row)

    result = conn.execute(
        "SELECT trial_key FROM movedb_catalog.osim_artifacts WHERE artifact_id = ?",
        [artifact_id],
    ).fetchone()

    assert result is not None
    assert result[0] is None, f"Expected trial_key to be NULL, got {result[0]}"


def test_initialize_catalog_is_idempotent() -> None:
    conn = duckdb.connect(":memory:")
    initialize_catalog(conn)

    register_osim_artifact(conn, make_test_row())
    initialize_catalog(conn)

    count = conn.execute("SELECT COUNT(*) FROM movedb_catalog.osim_artifacts").fetchone()[0]
    assert count == 1, f"Expected 1 row after re-init, got {count}"
