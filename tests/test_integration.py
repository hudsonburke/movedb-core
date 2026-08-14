"""Integration test — full ingestion and query workflow with BAA01 Baseline data.

Demonstrates how the schema hierarchy works end-to-end:
    1. Ingest C3D files → Parquet (with metadata enrichment)
    2. Load from Parquet (with schema validation)
    3. Define application-specific parameter schema
    4. Query across data (parameters ↔ points join)
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from movedb.ingestion.adapters.c3d import (
    read_events,
    read_forceplates,
    read_forceplate_geometry,
    read_analogs,
    read_points,
    read_parameters,
)
from movedb.ingestion.session import process_session
from movedb.schemas import (
    Analogs,
    Events,
    ForceplateGeometry,
    Forceplates,
    Points,
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

    def test_points_inherits_trial_metadata(self):
        assert issubclass(Points, TrialMetadata)

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

    def test_points_written(self, result, output_dir):
        assert "points" in result
        df = result["points"]
        assert len(df) > 0
        # Verify parquet exists and validates
        path = output_dir / SUBJECT_ID / "points.parquet"
        assert path.exists()
        loaded = pl.read_parquet(path)
        Points.validate(loaded)

    def test_points_have_residual_and_camera_mask(self, result):
        """Points should include quality data."""
        df = result["points"]
        assert "residual" in df.columns
        assert "camera_mask" in df.columns
        assert df["residual"].dtype == pl.Float64

    def test_forceplates_written(self, result, output_dir):
        assert "forceplates" in result
        df = result["forceplates"]
        assert len(df) > 0
        path = output_dir / SUBJECT_ID / "forceplates.parquet"
        assert path.exists()
        loaded = pl.read_parquet(path)
        Forceplates.validate(loaded)

    def test_forceplate_geometry_written(self, result, output_dir):
        assert "forceplate_geometry" in result
        df = result["forceplate_geometry"]
        assert len(df) > 0
        path = output_dir / SUBJECT_ID / "forceplate_geometry.parquet"
        assert path.exists()
        loaded = pl.read_parquet(path)
        ForceplateGeometry.validate(loaded)
        # 13 trials × 4 plates = 52 rows
        assert len(loaded) == 13 * 4

    def test_forceplate_geometry_has_corners(self, result):
        """Geometry should include corner positions."""
        df = result["forceplate_geometry"]
        # Each row should have 12 corner values (3×4)
        for corners in df["corners"]:
            assert len(corners) == 12

    def test_analogs_written(self, result, output_dir):
        assert "analogs" in result
        df = result["analogs"]
        assert len(df) > 0
        path = output_dir / SUBJECT_ID / "analogs.parquet"
        assert path.exists()
        loaded = pl.read_parquet(path)
        Analogs.validate(loaded)

    def test_events_written(self, result, output_dir):
        # Walk01-Walk15 have no events in these C3D files
        path = output_dir / SUBJECT_ID / "events.parquet"
        if "events" in result:
            loaded = pl.read_parquet(path)
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
        Parameters.validate(loaded, allow_superfluous_columns=True)

    def test_parameters_one_per_trial(self, result):
        """Each C3D file should produce one row in parameters.parquet."""
        df = result["parameters"]
        assert len(df) == 13
        assert df["trial_name"].n_unique() == 13

    def test_parameters_have_identity(self, result):
        """Every parameter row should carry the trial metadata."""
        df = result["parameters"]
        assert (df["subject_id"] == SUBJECT_ID).all()
        assert (df["session_id"] == SESSION_ID).all()
        assert df["trial_name"].null_count() == 0

    def test_points_have_identity(self, result):
        """Every point row should carry the trial metadata."""
        df = result["points"]
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

    def test_load_points_with_schema(self, db_path):
        df = pl.read_parquet(db_path / SUBJECT_ID / "points.parquet")
        Points.validate(df)
        assert "trial_name" in df.columns
        assert "subject_id" in df.columns
        assert "session_id" in df.columns
        assert "residual" in df.columns
        assert "camera_mask" in df.columns

    def test_load_parameters_with_extended_schema(self, db_path):
        """Load parameters and validate against application-specific schema."""
        df = pl.read_parquet(db_path / SUBJECT_ID / "parameters.parquet")
        RatParameters.validate(df, allow_superfluous_columns=True)
        assert "Mass" in df.columns
        assert "RFemurLength" in df.columns

    def test_filter_by_trial(self, db_path):
        """Query points for a specific trial."""
        df = pl.read_parquet(db_path / SUBJECT_ID / "points.parquet")
        walk01 = df.filter(pl.col("trial_name") == "Walk01")
        assert walk01["trial_name"].unique().to_list() == ["Walk01"]
        assert len(walk01) > 0

    def test_filter_by_session(self, db_path):
        """Query all points for a session."""
        df = pl.read_parquet(db_path / SUBJECT_ID / "points.parquet")
        session_df = df.filter(pl.col("session_id") == SESSION_ID)
        assert len(session_df) == len(df)

    def test_join_parameters_with_points(self, db_path):
        """Join parameters with points to get mass alongside point data."""
        points = pl.read_parquet(db_path / SUBJECT_ID / "points.parquet")
        params = pl.read_parquet(db_path / SUBJECT_ID / "parameters.parquet")

        joined = points.join(
            params.select("trial_name", "Mass", "RFemurLength"),
            on="trial_name",
        )

        assert "Mass" in joined.columns
        assert "RFemurLength" in joined.columns
        assert joined["Mass"].n_unique() == 1

    def test_filter_by_residual(self, db_path):
        """Query points with good tracking quality."""
        df = pl.read_parquet(db_path / SUBJECT_ID / "points.parquet")
        good_points = df.filter(pl.col("residual") < 1.0)
        assert len(good_points) > 0
        assert (good_points["residual"] < 1.0).all()

    def test_aggregate_across_trials(self, db_path):
        """Compute per-trial statistics."""
        points = pl.read_parquet(db_path / SUBJECT_ID / "points.parquet")

        per_trial = points.group_by("trial_name").agg([
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

        mean_force = fp.filter(
            pl.col("variable") == "force"
        ).group_by("fp_name").agg([
            pl.col("value").mean().alias("mean_force"),
        ])

        assert len(mean_force) == 4
        assert "mean_force" in mean_force.columns

    def test_forceplate_geometry_query(self, db_path):
        """Query force plate geometry."""
        geom = pl.read_parquet(db_path / SUBJECT_ID / "forceplate_geometry.parquet")
        ForceplateGeometry.validate(geom)
        # 13 trials × 4 plates = 52 rows
        assert len(geom) == 13 * 4
        # Each plate should have corners
        for corners in geom["corners"]:
            assert len(corners) == 12

    def test_analogs_query(self, db_path):
        """Query analog channel data."""
        analogs = pl.read_parquet(db_path / SUBJECT_ID / "analogs.parquet")
        Analogs.validate(analogs)
        # Should have channels
        assert analogs["channel_name"].n_unique() > 0
