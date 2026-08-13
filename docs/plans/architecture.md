# MoveDB Architecture Plan

## Vision

MoveDB is a generic biomechanics data library that provides:
1. **Ingestion** — C3D → Parquet conversion
2. **Storage** — Parquet with patito schema validation
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
├── schemas/             # patito models
│   └── models.py        # Markers, Forceplates, Events, Sessions
└── catalog/             # DuckDB queries + convenience methods
    └── query.py         # MoveDB class
```

## Schema Definitions (patito)

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

## Application-Specific Extensions

Applications can extend schemas using `.with_fields()`:

```python
# rat-hindlimb-mocap adds side column during conversion
ForceplatesWithSide = Forceplates.with_fields(side=str)

# Or after loading
df = pl.read_parquet("forceplates.parquet")
fp_with_side = ForceplatesWithSide.from_polars(df)
```

## MoveDB Class

Convenience layer on top of patito + DuckDB:

```python
class MoveDB:
    """Domain-specific interface for biomechanics data."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.conn = duckdb.connect()
        self._register_tables()
    
    def _register_tables(self):
        """Register all Parquet files as DuckDB tables."""
        for subject_dir in self.data_dir.iterdir():
            if subject_dir.is_dir():
                for parquet in subject_dir.glob("*.parquet"):
                    table_name = f"{subject_dir.name}_{parquet.stem}"
                    self.conn.execute(f"""
                        CREATE OR REPLACE TABLE {table_name} 
                        AS SELECT * FROM read_parquet('{parquet}')
                    """)
    
    # Convenience methods (domain-specific)
    def get_markers(self, subject_id: str, session: str = None) -> Markers:
        """Load markers with schema validation."""
        df = pl.read_parquet(self.data_dir / subject_id / "markers.parquet")
        if session:
            df = df.filter(pl.col("session_id") == session)
        return Markers.from_polars(df)
    
    def get_forceplates(self, subject_id: str, session: str = None) -> Forceplates:
        """Load force plates with schema validation."""
        df = pl.read_parquet(self.data_dir / subject_id / "forceplates.parquet")
        if session:
            df = df.filter(pl.col("session_id") == session)
        return Forceplates.from_polars(df)
    
    def get_events(self, subject_id: str, session: str = None) -> Events:
        """Load events with schema validation."""
        df = pl.read_parquet(self.data_dir / subject_id / "events.parquet")
        if session:
            df = df.filter(pl.col("session_id") == session)
        return Events.from_polars(df)
    
    # SQL query interface (cross-subject)
    def query(self, sql: str) -> pl.DataFrame:
        """Execute SQL query across all data."""
        return self.conn.execute(sql).pl()
    
    # Utility methods
    def subjects(self) -> list[str]:
        """List available subjects."""
        return sorted([d.name for d in self.data_dir.iterdir() if d.is_dir()])
    
    def sessions(self, subject_id: str) -> list[str]:
        """List available sessions for a subject."""
        df = pl.read_parquet(self.data_dir / subject_id / "sessions.parquet")
        return sorted(df["session_id"].unique().to_list())
```

## Data Flow

```
C3D files
  → movedb.ingestion.process_session()
  → Parquet files (markers, forceplates, events, sessions)
  → movedb.catalog.MoveDB (query + convenience)
  → rat-vml (analysis)
```

## How rat-vml Uses movedb

```python
from movedb import MoveDB

db = MoveDB(Path("data/processed"))

# Convenience (domain-specific)
markers = db.get_markers("BAA01", "baseline")  # Returns Markers model
events = db.get_events("BAA01", "baseline")     # Returns Events model

# SQL (cross-subject)
df = db.query("SELECT subject_id, AVG(mass) FROM sessions GROUP BY subject_id")

# Utility
subjects = db.subjects()
sessions = db.sessions("BAA01")
```

## Implementation Plan

### Phase 1: Schemas (PR 1)
- Add `schemas/models.py` with patito models
- Tests for schema validation

### Phase 2: Catalog (PR 2)
- Add `catalog/query.py` with MoveDB class
- DuckDB integration
- Convenience methods

### Phase 3: Cleanup (PR 3)
- Remove old code from rat-vml
- Update to use movedb.catalog.MoveDB

### Phase 4: Documentation (PR 4)
- README, API docs, examples

## Key Principles

1. **movedb is generic** — no rat-specific logic, no Vicon-specific logic
2. **Applications extend schemas** — use `.with_fields()` for extra columns
3. **MoveDB is convenience** — thin layer on top of patito + DuckDB
4. **rat-vml is thin** — just calls `db.query()` and `db.get_markers()`
