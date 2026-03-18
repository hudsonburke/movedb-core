from __future__ import annotations

from pathlib import Path

import polars as pl

from movedb.catalog import connect_catalog, discover_session_bundle, open_bundle, register_session_bundle
from movedb.core import SessionParameters
from movedb.storage import write_events_parquet, write_parameters_parquet


class ExampleSessionParameters(SessionParameters):
    mass_kg: float


def test_discover_session_bundle_reports_canonical_files(tmp_path: Path) -> None:
    motion_dir = tmp_path / "sub-01" / "ses-01" / "motion"
    write_parameters_parquet(
        ExampleSessionParameters(subject_id="sub-01", session_id="ses-01", mass_kg=0.33),
        motion_dir / "parameters.parquet",
    )
    write_events_parquet(
        pl.DataFrame(
            {
                "trial_name": ["Walk01"],
                "context": ["Left"],
                "label": ["Foot Strike"],
                "time": [0.1],
                "frame": [1],
                "description": [None],
            }
        ),
        motion_dir / "events.parquet",
    )

    descriptor = discover_session_bundle(motion_dir)

    assert descriptor.subject_id == "sub-01"
    assert descriptor.session_id == "ses-01"
    assert {file.file_kind for file in descriptor.files} == {"parameters", "events"}


def test_register_session_bundle_creates_catalog_rows_and_views(tmp_path: Path) -> None:
    motion_dir = tmp_path / "sub-02" / "ses-03" / "motion"
    write_parameters_parquet(
        ExampleSessionParameters(subject_id="sub-02", session_id="ses-03", mass_kg=0.42),
        motion_dir / "parameters.parquet",
    )
    write_events_parquet(
        pl.DataFrame(
            {
                "subject_id": ["sub-02"],
                "session_id": ["ses-03"],
                "trial_name": ["Walk02"],
                "context": ["Right"],
                "label": ["Foot Strike"],
                "time": [0.2],
                "frame": [2],
                "description": [None],
            }
        ),
        motion_dir / "events.parquet",
    )

    conn = connect_catalog(tmp_path / "catalog.duckdb")
    register_session_bundle(conn, motion_dir)

    session_count = conn.execute("SELECT COUNT(*) FROM movedb_catalog.sessions").fetchone()[0]
    file_count = conn.execute("SELECT COUNT(*) FROM movedb_catalog.session_files").fetchone()[0]
    trial_rows = conn.execute(
        "SELECT subject_id, session_id, trial_name FROM movedb_catalog.trials"
    ).fetchall()

    assert session_count == 1
    assert file_count == 2
    assert trial_rows == [("sub-02", "ses-03", "Walk02")]


def test_open_bundle_creates_session_local_views(tmp_path: Path) -> None:
    motion_dir = tmp_path / "sub-05" / "ses-07" / "motion"
    write_parameters_parquet(
        ExampleSessionParameters(subject_id="sub-05", session_id="ses-07", mass_kg=0.5),
        motion_dir / "parameters.parquet",
    )

    conn = open_bundle(motion_dir)
    rows = conn.execute("SELECT subject_id, session_id, mass_kg FROM session_parameters").fetchall()

    assert rows == [("sub-05", "ses-07", 0.5)]
