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

### storage/parquet.py
**Input:** Parquet files on disk
**Output:** Typed DataFrames

```python
class ParquetStore:
    """Read/write Parquet with consistent schema."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
    
    def get_markers(self, subject_id: str, session: str = None) -> pl.DataFrame:
        """Load markers for a subject/session."""
    
    def get_forceplates(self, subject_id: str, session: str = None) -> pl.DataFrame:
        """Load force plates for a subject/session."""
    
    def get_events(self, subject_id: str, session: str = None) -> pl.DataFrame:
        """Load events for a subject/session."""
    
    def get_sessions(self, subject_id: str = None) -> pl.DataFrame:
        """Load session parameters."""
    
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

### markers.parquet
| Column | Type | Description |
|--------|------|-------------|
| frame | i64 | Frame number |
| time | f64 | Time in seconds |
| marker_name | str | Marker name |
| x, y, z | f64 | Position (mm) |
| trial_name | str | Trial name |
| subject_id | str | Subject ID |
| session_id | str | Session ID |

### forceplates.parquet
| Column | Type | Description |
|--------|------|-------------|
| frame | i64 | Frame number |
| time | f64 | Time in seconds |
| fp_name | str | Force plate name |
| variable | str | force, moment, cop, free_moment |
| axis | str | x, y, z |
| value | f64 | Value |
| side | str | Left, Right, unknown |
| trial_name | str | Trial name |
| subject_id | str | Subject ID |
| session_id | str | Session ID |

### events.parquet
| Column | Type | Description |
|--------|------|-------------|
| context | str | Left, Right |
| label | str | Foot Strike, Foot Off |
| time | f64 | Time in seconds |
| trial_name | str | Trial name |
| subject_id | str | Subject ID |
| session_id | str | Session ID |

### sessions.parquet
| Column | Type | Description |
|--------|------|-------------|
| subject_id | str | Subject ID |
| session_id | str | Session ID |
| Mass | f64 | Mass (kg) |
| RFemurLength | f64 | Right femur length (mm) |
| RTibiaLength | f64 | Right tibia length (mm) |
| ... | ... | ... |
