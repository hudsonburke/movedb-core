# MoveDB

A Python library for biomechanics data management using Parquet-based storage and DuckDB catalog queries.

## Architecture

```
Storage Layer (Parquet):
├── markers.parquet        # Marker positions (wide or long format)
├── forceplates.parquet    # Force plate data (forces, moments, COP)
├── kinematics.parquet     # IK results (joint angles)
├── grf.parquet            # Ground reaction forces
├── events.parquet         # Gait events (foot strike/off)
├── parameters.parquet     # Session parameters (mass, height, etc.)
└── analogs.parquet        # Analog signals

Catalog Layer (DuckDB):
├── sessions               # All sessions with metadata
├── trials                 # All trials with quality metrics
├── session_files          # File registry (what files exist where)
├── session_metrics        # Quality metrics per session
├── trial_metrics          # Quality metrics per trial
└── views                  # Pre-built SQL queries

Core Models:
├── KinematicsData         # Joint positions, velocities, accelerations, torques
├── ForceplateData         # Forces, moments, COP, calibration matrices
├── MarkerData             # Marker positions
├── EventData              # Gait events
├── GRFData                # Ground reaction forces
└── AnalogData             # Analog signals
```

## Data Directory Convention

Raw and processed data should be stored in separate directories:

```
data/
├── raw/                   # Original C3D/B3D files (immutable)
│   ├── sourcedata/
│   └── ...
├── processed/             # Parquet files, DuckDB catalog
│   ├── markers.parquet
│   ├── forceplates.parquet
│   ├── catalog.db
│   └── ...
└── results/               # Analysis outputs (IK, ID, Moco)
    ├── ik/
    ├── id/
    └── moco/
```

This separation ensures:
- Raw data is never modified
- Processed data can be regenerated from raw
- Results are clearly separated from source data

## Installation

```bash
# Clone and install in development mode
git clone https://github.com/hudsonburke/movedb.git
cd movedb
pip install -e .

# For C3D file support
pip install -e ".[c3d]"

# For B3D file support
pip install -e ".[b3d]"
```

## Usage

### Storage Layer

```python
from movedb.storage import write_markers_parquet, read_markers_parquet
from movedb.core import MarkerData, MarkerMeta

# Write markers to Parquet
meta = MarkerMeta(
    marker_names=["r_asis", "l_asis", "r_knee", "l_knee"],
    rate=200.0,
    units="mm",
)
write_markers_parquet(df, "markers.parquet", format="wide", metadata=meta)

# Read markers from Parquet
df = read_markers_parquet("markers.parquet")
```

### Catalog Layer

```python
from movedb.catalog import connect_catalog, register_session_bundle

# Create a catalog
conn = connect_catalog("catalog.db")

# Register a session bundle
register_session_bundle(conn, "/path/to/session")

# Query trials
result = conn.execute("SELECT * FROM trials WHERE qualifies_for_ik = TRUE")
```

### Core Models

```python
from movedb.core import KinematicsData, MarkerData, EventData

# Create kinematics data
kin = KinematicsData(
    names=["hip_flexion_r", "knee_angle_r"],
    rate=200.0,
    units="rad",
    pos=pos_array,  # (n_frames, 2)
    vel=vel_array,
    acc=acc_array,
    tau=tau_array,
)
```

## Data Flow

```
C3D files → Parquet storage → DuckDB catalog → Analysis pipeline
                                                    ↓
                                            IK/ID/MocoInverse
                                                    ↓
                                            Results (Parquet)
```

## Dependencies

- `numpy` — Array operations
- `numpydantic` — Type-safe array validation
- `pydantic` — Data model validation
- `patito` — Polars DataFrame validation
- `polars` — DataFrame operations
- `duckdb` — Catalog queries
- `click` — CLI interface

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## License

MIT
