from __future__ import annotations

from pathlib import Path

from movedb.catalog import connect_catalog, write_session_quality, write_trial_quality


def test_catalog_quality_tables_and_views(tmp_path: Path) -> None:
    conn = connect_catalog(tmp_path / "catalog.duckdb")

    write_session_quality(
        conn,
        [
            {
                "session_key": "sub-01_ses-01",
                "session_dir": "sub-01/ses-01/motion",
                "subject_id": "sub-01",
                "session_id": "ses-01",
                "qualifies_for_osim": True,
                "static_trial": "Static01",
                "reason": "qualified_for_osim",
                "motion_dir": "sub-01/ses-01/motion",
                "opensim_dir": "sub-01/ses-01/opensim",
                "mass_kg": 0.35,
            }
        ],
    )
    write_trial_quality(
        conn,
        [
            {
                "trial_key": "sub-01_ses-01_Walk01",
                "session_key": "sub-01_ses-01",
                "subject_id": "sub-01",
                "session_id": "ses-01",
                "trial_name": "Walk01",
                "qualifies_for_ik": True,
                "qualifies_for_id": False,
                "reason": "qualified_for_ik",
                "t_start": 0.1,
                "t_end": 1.2,
                "motion_dir": "sub-01/ses-01/motion",
                "opensim_dir": "sub-01/ses-01/opensim",
                "has_fp_mapping": False,
                "fp_mapping": "null",
                "enf_notes": "",
            }
        ],
    )

    osim_sessions = conn.execute(
        "SELECT session_key, qualifies_for_osim FROM movedb_catalog.osim_sessions"
    ).fetchall()
    qualified_trials = conn.execute(
        "SELECT trial_key, qualifies_for_ik, qualifies_for_id FROM movedb_catalog.qualified_trials"
    ).fetchall()
    id_trials = conn.execute("SELECT COUNT(*) FROM movedb_catalog.id_trials").fetchone()[0]

    assert osim_sessions == [("sub-01_ses-01", True)]
    assert qualified_trials == [("sub-01_ses-01_Walk01", True, False)]
    assert id_trials == 0
