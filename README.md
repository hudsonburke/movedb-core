<p align="center">
  <img src="imgs/movedb-logo-cropped.png" alt="MoveDB Logo" width="400"/>
  <h1 align="center">MoveDB</h1>
</p>

<h3 align="center">Biomechanics data management with Parquet storage and DuckDB queries</h3>

---

## Overview

MoveDB reads biomechanics data from C3D files, stores it as Parquet, and queries it through DuckDB. Schemas are defined using [patito](https://github.com/JakobGM/patito) (pydantic + polars), giving you type-safe DataFrames with validation at both ingestion and query time.

```
C3D files → Adapters (read_points, read_forceplates, ...) → Parquet files → DuckDB queries
```

## Architecture

### Schema hierarchy

All schemas are [patito Models](https://patito.readthedocs.io/) — pydantic schemas that double as Polars DataFrame validators.

```
TrialMetadata (trial_name, subject_id, session_id)
├── Points              — 3D marker positions + residuals + camera masks
├── Forceplates         — force, moment, COP per frame
├── ForceplateGeometry  — origin, corners, calibration matrix per plate
├── Analogs             — raw analog channels (EMG, voltage)
├── Events              — gait events (foot strike/off)
└── Parameters          — extensible PROCESSING/TRIAL/ANALOG parameters
```

`TrialMetadata` is the base for all trial-level records. `Parameters` is extensible for project-specific fields:

```python
from movedb.schemas import Parameters

RatParameters = Parameters.with_fields(
    Mass=(float, ...),
    RFemurLength=(float, ...),
    RTibiaLength=(float, ...),
)
```

### Parquet layout

```
processed/
└── <SubjectName>/
    ├── points.parquet              # per (frame, marker) × trial
    ├── forceplates.parquet         # per (frame, plate, variable, axis) × trial
    ├── forceplate_geometry.parquet # per (trial, plate)
    ├── analogs.parquet             # per (frame, channel) × trial
    ├── events.parquet              # per event × trial
    └── parameters.parquet          # per trial
```

### Adapter layer

Adapters extract data from C3D files into patito DataFrames without metadata — the caller enriches with `subject_id`/`session_id`.

```python
from movedb.ingestion.adapters.c3d import read_points, read_forceplates

# Adapter returns pure C3D data (validated against PointsData schema)
df = read_points(c3d_path, trial_name="Walk01")

# Caller adds metadata
df = df.with_columns([
    pl.lit("SubjectName").alias("subject_id"),
    pl.lit("SessionName").alias("session_id"),
])
```

### Catalog layer

DuckDB queries parquet files directly — no table registration, automatic filter pushdown.

```python
from movedb import MoveDB

db = MoveDB(Path("processed"))

# Query with filter pushdown
points = db.get_points("SubjectName", session="SessionName")

# Column pruning (only reads what you need)
df = db.get_points("SubjectName", columns=["frame", "x", "y", "z"])

# Cross-subject query
df = db.query("SELECT subject_id, Mass FROM parameters GROUP BY subject_id")

# Discovery
subjects = db.subjects()
sessions = db.sessions("SubjectName")
trials = db.trials("SubjectName", session="SessionName")
```

## Installation

```bash
git clone https://github.com/hudsonburke/movedb-core.git
cd movedb-core
uv pip install -e .
```

## Quick start

### Ingest a session

```python
from movedb.ingestion.session import process_session
from pathlib import Path

result = process_session(
    subject_id="SubjectName",
    session="SessionName",
    c3d_files=sorted(Path("data/raw/SubjectName/SessionName").glob("*.c3d")),
    output_dir=Path("data/processed"),
)

# result contains DataFrames for each data type
print(f"Points: {len(result['points'])} rows")
print(f"Forceplates: {len(result['forceplates'])} rows")
print(f"Parameters: {len(result['parameters'])} rows")
```

### Query the catalog

```python
from movedb import MoveDB

db = MoveDB(Path("data/processed"))

# List available data
subjects = db.subjects()
sessions = db.sessions("SubjectName")

# Load with schema validation (returns patito DataFrame)
points = db.get_points("SubjectName", session="SessionName")

# Join parameters with points
import polars as pl
points = db.get_points("SubjectName")
params = db.get_parameters("SubjectName")
joined = points.join(
    params.select("trial_name", "Mass", "RFemurLength"),
    on="trial_name",
)

# Filter by data quality
good_points = points.filter(pl.col("residual") < 1.0)

# Aggregate across trials
per_trial = points.group_by("trial_name").agg([
    pl.col("x").mean().alias("mean_x"),
    pl.len().alias("n_rows"),
])
```

### Extend parameters for your project

```python
from movedb.schemas import Parameters

# Define project-specific schema using patito
RatParameters = Parameters.with_fields(
    Mass=(float, ...),
    RFemurLength=(float, ...),
    RTibiaLength=(float, ...),
    LFemurLength=(float, ...),
    LTibiaLength=(float, ...),
)

# Validate against your schema
params = db.get_parameters("SubjectName")
RatParameters.validate(params, allow_superfluous_columns=True)
```

## Data directory convention

```
data/
├── raw/                         # Original C3D files (immutable)
│   └── <SubjectName>/
│       └── <SessionName>/
│           ├── Walk01.c3d
│           └── ...
└── processed/                   # Parquet output
    └── <SubjectName>/
        ├── points.parquet
        ├── forceplates.parquet
        ├── forceplate_geometry.parquet
        ├── analogs.parquet
        ├── events.parquet
        └── parameters.parquet
```

## Schemas

All schemas are defined as [patito Models](https://patito.readthedocs.io/) in `movedb/schemas/models.py`. Patito combines pydantic and polars, giving you:

- **Type-annotated fields** that map to Polars dtypes
- **DataFrame validation** via `Schema.validate(df)`
- **Mock data generation** via `Schema.example()`
- **Schema extension** via `Schema.with_fields()`

```python
from movedb.schemas import Points, Forceplates, Parameters

# Validate a DataFrame
Points.validate(df)

# Extend with project-specific fields
RatParameters = Parameters.with_fields(Mass=(float, ...))

# Generate example data for tests
example = Points.example()
```

## Development

```bash
uv pip install -e ".[dev]"
uv run pytest tests/
```

## License

MIT
