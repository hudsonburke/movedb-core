from __future__ import annotations

from pathlib import Path

from movedb.core import SessionParameters
from movedb.storage import (
    parameters_to_polars,
    read_parameters_json,
    read_parameters_parquet,
    read_session_parameters,
    write_parameters_json,
    write_parameters_parquet,
)


class ExampleSessionParameters(SessionParameters):
    mass_kg: float
    right_femur_length_mm: float


def test_session_parameters_roundtrip_json_and_parquet(tmp_path: Path) -> None:
    params = ExampleSessionParameters(
        subject_id="sub-01",
        session_id="ses-01",
        source_file="session.mp",
        mass_kg=0.35,
        right_femur_length_mm=42.0,
        treatment_group="sham",
    )

    json_path = write_parameters_json(params, tmp_path / "parameters.json")
    parquet_path = write_parameters_parquet(params, tmp_path / "parameters.parquet")

    loaded_json = read_parameters_json(json_path, ExampleSessionParameters)
    loaded_parquet, storage_metadata = read_parameters_parquet(parquet_path, ExampleSessionParameters)

    assert loaded_json.mass_kg == 0.35
    assert loaded_json.extras["treatment_group"] == "sham"
    assert loaded_parquet.right_femur_length_mm == 42.0
    assert loaded_parquet.extras["treatment_group"] == "sham"
    assert storage_metadata is not None
    assert storage_metadata.schema_name == "session_parameters"


def test_parameters_to_polars_flattens_extras() -> None:
    params = ExampleSessionParameters(
        mass_kg=0.4,
        right_femur_length_mm=40.0,
        cohort="pilot",
    )

    df = parameters_to_polars(params)

    assert df.height == 1
    assert df["parameter_schema"][0] == "ExampleSessionParameters"
    assert df["extras_json"][0] is not None


def test_read_session_parameters_uses_motion_directory(tmp_path: Path) -> None:
    params = ExampleSessionParameters(
        subject_id="sub-02",
        session_id="ses-03",
        mass_kg=0.42,
        right_femur_length_mm=41.0,
    )
    motion_dir = tmp_path / "sub-02" / "ses-03" / "motion"
    write_parameters_parquet(params, motion_dir / "parameters.parquet")

    loaded, metadata = read_session_parameters(motion_dir, ExampleSessionParameters)

    assert loaded.subject_id == "sub-02"
    assert loaded.session_id == "ses-03"
    assert loaded.mass_kg == 0.42
    assert metadata is not None
    assert metadata.schema_name == "session_parameters"
