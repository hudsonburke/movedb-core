from __future__ import annotations

from pathlib import Path

import polars as pl

from movedb.catalog import (
    connect_catalog,
    discover_session_bundle,
    open_bundle,
    register_dataset_root,
    register_session_bundle,
)
from movedb.core import AnalogMeta, SessionParameters
from movedb.storage import write_analogs_parquet, write_events_parquet, write_parameters_parquet


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


def test_register_dataset_root_builds_inventory_and_trial_manifest(tmp_path: Path) -> None:
    motion_a = tmp_path / "sub-10" / "ses-baseline" / "motion"
    motion_b = tmp_path / "sub-10" / "ses-week12" / "motion"

    write_parameters_parquet(
        ExampleSessionParameters(subject_id="sub-10", session_id="ses-baseline", mass_kg=0.31),
        motion_a / "parameters.parquet",
    )
    write_events_parquet(
        pl.DataFrame(
            {
                "subject_id": ["sub-10", "sub-10"],
                "session_id": ["ses-baseline", "ses-baseline"],
                "trial_name": ["Walk01", "Walk02"],
                "context": ["Left", "Right"],
                "label": ["Foot Strike", "Foot Strike"],
                "time": [0.1, 0.2],
                "frame": [1, 2],
                "description": [None, None],
            }
        ),
        motion_a / "events.parquet",
    )

    write_parameters_parquet(
        ExampleSessionParameters(subject_id="sub-10", session_id="ses-week12", mass_kg=0.45),
        motion_b / "parameters.parquet",
    )
    analog_df = pl.DataFrame(
        {
            "trial_name": ["Walk03"],
            "frame": [1],
            "time": [0.0],
            "EMG1": [1.0],
        }
    )
    write_analogs_parquet(
        analog_df,
        motion_b / "analogs.parquet",
        format="wide",
        metadata=AnalogMeta(rate=1000.0, first_frame=1, names=["EMG1"], units=["V"]),
    )

    conn = connect_catalog(tmp_path / "catalog.duckdb")
    register_dataset_root(conn, tmp_path)

    inventory = conn.execute(
        """
        SELECT session_id, has_parameters, has_events, has_analogs
        FROM movedb_catalog.session_inventory
        ORDER BY session_id
        """
    ).fetchall()
    manifest = conn.execute(
        """
        SELECT session_id, trial_name, event_count, has_parameters, has_events
        FROM movedb_catalog.trial_manifest
        ORDER BY trial_name
        """
    ).fetchall()

    assert inventory == [
        ("ses-baseline", 1, 1, 0),
        ("ses-week12", 1, 0, 1),
    ]
    assert manifest == [
        ("ses-baseline", "Walk01", 1, 1, 1),
        ("ses-baseline", "Walk02", 1, 1, 1),
    ]
