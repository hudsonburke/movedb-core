# MoveDB Architecture Plan

## Vision

MoveDB is a generic biomechanics data library that provides:
1. **Ingestion** — C3D → Parquet conversion
2. **Storage** — Consistent Parquet schema with typed columns
3. **Querying** — DuckDB interface for cross-subject analysis

It is **not** rat-specific. It works for any motion capture dataset.

## Current State

```
movedb-core/
├── ingestion/
│   └── session.py      # process_session() — C3D → Parquet
├── adapters/
│   ├── c3d.py          # C3D parsing
│   └── polars.py       # Polars conversion
└── core/
    └── models.py       # Pydantic data models
```

## Target Architecture

```
movedb-core/
├── ingestion/           # C3D → Parquet
│   ├── session.py       # process_session()
│   └── enf.py           # .enf parsing (generic utility)
├── storage/             # Parquet read/write
│   ├── parquet.py       # Read/write with consistent schema
│   └── schema.py        # Column definitions
├── catalog/             # DuckDB queries
│   ├── build.py         # Build catalog from Parquet
│   └── query.py         # SQL queries across subjects/sessions
└── core/                # Data models
    └── models.py        # Pydantic models
```

## Module Responsibilities

### ingestion/session.py
**Input:** C3D files (from tar.gz or direct)
**Output:** Parquet files (markers, forceplates, events, sessions)

```python
def process_session(
    subject_id: str,
    session: str,
    c3d_files: list[Path],
    output_dir: Path,
) -> dict[str, pl.DataFrame]:
    """Convert C3D files to Parquet."""
    # Extract markers, forceplates, events from each C3D
    # Extract PROCESSING parameters for sessions.parquet
    # Write to {output_dir}/{subject_id}/*.parquet
```

### storage/schemas.py
**Input:** Data validation
**Output:** Patito model definitions

```python
import patito as pt

class Markers(pt.Model):
    frame: int
    time: float
    marker_name: str
    x: float
    y: float
    z: float
    trial_name: str
    subject_id: str
    session_id: str

class Forceplates(pt.Model):
    frame: int
    time: float
    fp_name: str
    variable: str
    axis: str
    value: float
    side: str | None = None
    trial_name: str
    subject_id: str
    session_id: str

class Events(pt.Model):
    context: str
    label: str
    time: float
    trial_name: str
    subject_id: str
    session_id: str

class Sessions(pt.Model):
    subject_id: str
    session_id: str
    Mass: float | None = None
    RFemurLength: float | None = None
    RTibiaLength: float | None = None
    # ... other parameters
```

### storage/parquet.py
**Input:** Parquet files on disk
**Output:** Typed DataFrames

```python
class ParquetStore:
    """Read/write Parquet with schema validation."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
    
    def get_markers(self, subject_id: str, session: str = None) -> Markers:
        """Load markers with schema validation."""
    
    def get_forceplates(self, subject_id: str, session: str = None) -> Forceplates:
        """Load force plates with schema validation."""
    
    def get_events(self, subject_id: str, session: str = None) -> Events:
        """Load events with schema validation."""
    
    def get_sessions(self, subject_id: str = None) -> Sessions:
        """Load session parameters with schema validation."""
    
    def subjects(self) -> list[str]:
        """List available subjects."""
    
    def sessions(self, subject_id: str) -> list[str]:
        """List available sessions for a subject."""
```

### catalog/query.py
**Input:** SQL queries
**Output:** DataFrames

```python
class MoveDB:
    """DuckDB interface for querying motion capture data."""
    
    def __init__(self, data_dir: Path):
        self.store = ParquetStore(data_dir)
        self._register_tables()
    
    def query(self, sql: str) -> pl.DataFrame:
        """Execute SQL query across all data."""
    
    def find_valid_trials(self, side: str = "right") -> pl.DataFrame:
        """Find trials with correct event sequence."""
    
    def get_trial_data(self, subject_id: str, session: str, trial: str) -> dict:
        """Get all data for a specific trial."""
```

## Data Flow

```
C3D files
  → movedb.ingestion.process_session()
  → Parquet files (markers, forceplates, events, sessions)
  → movedb.storage.ParquetStore (read/write)
  → movedb.catalog.MoveDB (query)
  → rat-vml (analysis)
```

## How rat-vml Uses movedb

```python
from movedb.catalog import MoveDB

db = MoveDB(Path("data/processed"))

# Find valid walking trials
trials = db.find_valid_trials(side="right")

# Get markers for a trial
markers = db.get_markers("BAA01", "baseline")

# SQL query across subjects
df = db.query("""
    SELECT subject_id, session_id, 
           AVG(mass) as avg_mass
    FROM sessions 
    GROUP BY subject_id, session_id
""")
```

## Implementation Plan

### Phase 1: Storage Layer (PR 1)
- Add `storage/parquet.py` with `ParquetStore` class
- Consistent read/write for markers, forceplates, events, sessions
- Tests for schema validation

### Phase 2: Catalog Layer (PR 2)
- Add `catalog/query.py` with `MoveDB` class
- DuckDB integration for SQL queries
- Pre-built queries: `find_valid_trials()`, `get_trial_data()`
- Tests for query correctness

### Phase 3: Cleanup (PR 3)
- Remove old code (queries.py, io.py in rat-vml)
- Update rat-vml to use movedb.catalog.MoveDB
- Update imports

### Phase 4: Documentation (PR 4)
- Update README with usage examples
- Add API documentation
- Example notebooks

## Parquet Schema

### Parquet Schemas (defined in storage/schemas.py)

All schemas use patito Models for type validation:

- **Markers**: frame, time, marker_name, x, y, z, trial_name, subject_id, session_id
- **Forceplates**: frame, time, fp_name, variable, axis, value, side (optional), trial_name, subject_id, session_id
- **Events**: context, label, time, trial_name, subject_id, session_id
- **Sessions**: subject_id, session_id, Mass, RFemurLength, RTibiaLength, ... (optional parameters)
