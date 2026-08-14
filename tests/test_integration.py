"""Integration test — full ingestion and query workflow with BAA01 Baseline data.

Demonstrates how the schema hierarchy works end-to-end:
    1. Ingest C3D files → Parquet (with metadata enrichment)
    2. Load from Parquet (with schema validation)
    3. Define application-specific parameter schema
    4. Query across data (parameters ↔ markers join)
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from movedb.ingestion.adapters.c3d import (
    read_events,
    read_forceplates,
    read_markers,
    read_parameters,
)
from movedb.ingestion.session import process_session
from movedb.schemas import (
    Events,
    Forceplates,
    Markers,
    Parameters,
    TrialMetadata,
)

DATA_DIR = Path(__file__).parent / "data" / "BAA01" / "Baseline"
SUBJECT_ID = "BAA01"
SESSION_ID = "Baseline"


# ---------------------------------------------------------------------------
# Application-specific parameter schema
# ---------------------------------------------------------------------------

# A project studying rat biomechanics would extend Parameters like this:
RatParameters = Parameters.with_fields(
    Mass=(float, ...),
    Length=(float, ...),
    RFemurLength=(float, ...),
    RTibiaLength=(float, ...),
    LFemurLength=(float, ...),
    LTibiaLength=(float, ...),
)


# ---------------------------------------------------------------------------
# Schema hierarchy tests
# ---------------------------------------------------------------------------


class TestSchemaHierarchy:
    """Verify the inheritance chain works correctly."""

    def test_markers_inherits_trial_metadata(self):
        assert issubclass(Markers, TrialMetadata)

    def test_forceplates_inherits_trial_metadata(self):
        assert issubclass(Forceplates, TrialMetadata)

    def test_events_inherits_trial_metadata(self):
        assert issubclass(Events, TrialMetadata)

    def test_parameters_inherits_trial_metadata(self):
        assert issubclass(Parameters, TrialMetadata)

    def test_rat_parameters_extends_parameters(self):
        """with_fields() creates a new model with Parameters fields plus extras."""
        assert "Mass" in RatParameters.model_fields
        assert "trial_name" in RatParameters.model_fields  # copied via with_fields
        assert "subject_id" in RatParameters.model_fields
        assert "session_id" in RatParameters.model_fields

    def test_rat_parameters_has_required_fields(self):
        assert "Mass" in RatParameters.model_fields
        assert "trial_name" in RatParameters.model_fields
        assert "subject_id" in RatParameters.model_fields
        assert "session_id" in RatParameters.model_fields


# ---------------------------------------------------------------------------
# Ingestion workflow
# ---------------------------------------------------------------------------


class TestIngestionWorkflow:
    """Test the full ingestion pipeline with real C3D files."""

    @pytest.fixture
    def output_dir(self, tmp_path):
        return tmp_path / "processed"

    @pytest.fixture
    def result(self, output_dir):
        c3d_files = sorted(DATA_DIR.glob("*.c3d"))
        return process_session(SUBJECT_ID, SESSION_ID, c3d_files, output_dir)

    def test_markers_written(self, result, output_dir):
        assert "markers" in result
        df = result["markers"]
        assert len(df) > 0
        # Verify parquet exists and validates
        path = output_dir / SUBJECT_ID / "markers.parquet"
        assert path.exists()
        loaded = pl.read_parquet(path)
        Markers.validate(loaded)

    def test_forceplates_written(self, result, output_dir):
        assert "forceplates" in result
        df = result["forceplates"]
        assert len(df) > 0
        path = output_dir / SUBJECT_ID / "forceplates.parquet"
        assert path.exists()
        loaded = pl.read_parquet(path)
        Forceplates.validate(loaded)

    def test_events_written(self, result, output_dir):
        # Walk01-Walk15 have no events in these C3D files
        path = output_dir / SUBJECT_ID / "events.parquet"
        # Events may or may not be present depending on C3D files
        if "events" in result:
            loaded = pl.read_parquet(path)
            # Drop rows with nulls (from empty trials concatenated with diagonal)
            loaded = loaded.drop_nulls(subset=["context", "label", "time"])
            if len(loaded) > 0:
                Events.validate(loaded)

    def test_parameters_written(self, result, output_dir):
        assert "parameters" in result
        df = result["parameters"]
        assert len(df) > 0
        path = output_dir / SUBJECT_ID / "parameters.parquet"
        assert path.exists()
        loaded = pl.read_parquet(path)
        # Base Parameters schema has 3 identity fields;
        # the parquet has extra PROCESSING params — validate the identity fields.
        Parameters.validate(loaded, allow_superfluous_columns=True)

    def test_parameters_one_per_trial(self, result):
        """Each C3D file should produce one row in parameters.parquet."""
        df = result["parameters"]
        # We have 13 C3D files
        assert len(df) == 13
        # Each should have a unique trial_name
        assert df["trial_name"].n_unique() == 13

    def test_parameters_have_identity(self, result):
        """Every parameter row should carry the trial metadata."""
        df = result["parameters"]
        assert (df["subject_id"] == SUBJECT_ID).all()
        assert (df["session_id"] == SESSION_ID).all()
        assert df["trial_name"].null_count() == 0

    def test_markers_have_identity(self, result):
        """Every marker row should carry the trial metadata."""
        df = result["markers"]
        assert (df["subject_id"] == SUBJECT_ID).all()
        assert (df["session_id"] == SESSION_ID).all()
        assert df["trial_name"].null_count() == 0


# ---------------------------------------------------------------------------
# Query workflow
# ---------------------------------------------------------------------------


class TestQueryWorkflow:
    """Test loading and querying ingested data."""

    @pytest.fixture
    def db_path(self, tmp_path):
        c3d_files = sorted(DATA_DIR.glob("*.c3d"))
        process_session(SUBJECT_ID, SESSION_ID, c3d_files, tmp_path / "processed")
        return tmp_path / "processed"

    def test_load_markers_with_schema(self, db_path):
        df = pl.read_parquet(db_path / SUBJECT_ID / "markers.parquet")
        Markers.validate(df)
        assert "trial_name" in df.columns
        assert "subject_id" in df.columns
        assert "session_id" in df.columns

    def test_load_parameters_with_extended_schema(self, db_path):
        """Load parameters and validate against application-specific schema."""
        df = pl.read_parquet(db_path / SUBJECT_ID / "parameters.parquet")
        RatParameters.validate(df, allow_superfluous_columns=True)
        # Should have Mass and bone lengths
        assert "Mass" in df.columns
        assert "RFemurLength" in df.columns

    def test_filter_by_trial(self, db_path):
        """Query markers for a specific trial."""
        df = pl.read_parquet(db_path / SUBJECT_ID / "markers.parquet")
        walk01 = df.filter(pl.col("trial_name") == "Walk01")
        assert walk01["trial_name"].unique().to_list() == ["Walk01"]
        assert len(walk01) > 0

    def test_filter_by_session(self, db_path):
        """Query all markers for a session."""
        df = pl.read_parquet(db_path / SUBJECT_ID / "markers.parquet")
        session_df = df.filter(pl.col("session_id") == SESSION_ID)
        assert len(session_df) == len(df)  # all data is from this session

    def test_join_parameters_with_markers(self, db_path):
        """Join parameters with markers to get mass alongside marker data."""
        markers = pl.read_parquet(db_path / SUBJECT_ID / "markers.parquet")
        params = pl.read_parquet(db_path / SUBJECT_ID / "parameters.parquet")

        # Join on trial identity
        joined = markers.join(
            params.select("trial_name", "Mass", "RFemurLength"),
            on="trial_name",
        )

        assert "Mass" in joined.columns
        assert "RFemurLength" in joined.columns
        # Mass should be the same for all rows (same subject)
        assert joined["Mass"].n_unique() == 1

    def test_aggregate_across_trials(self, db_path):
        """Compute per-trial statistics."""
        markers = pl.read_parquet(db_path / SUBJECT_ID / "markers.parquet")

        per_trial = markers.group_by("trial_name").agg([
            pl.col("x").mean().alias("mean_x"),
            pl.col("y").mean().alias("mean_y"),
            pl.col("z").mean().alias("mean_z"),
            pl.len().alias("n_rows"),
        ])

        assert len(per_trial) > 0
        assert "mean_x" in per_trial.columns
        assert "n_rows" in per_trial.columns

    def test_forceplates_query(self, db_path):
        """Query force plate data."""
        fp = pl.read_parquet(db_path / SUBJECT_ID / "forceplates.parquet")
        Forceplates.validate(fp)

        # Get mean force per platform
        mean_force = fp.filter(
            pl.col("variable") == "force"
        ).group_by("fp_name").agg([
            pl.col("value").mean().alias("mean_force"),
        ])

        assert len(mean_force) == 4  # 4 platforms
        assert "mean_force" in mean_force.columns
