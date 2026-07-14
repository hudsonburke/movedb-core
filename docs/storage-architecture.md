# Storage Architecture

MoveDB uses a Parquet-first architecture with DuckDB as the root-level
orchestration and query layer.

## Direction

- Canonical session motion files stay in wide/struct form.
- Analytical projections use long/row-oriented schemas.
- Patito is used where schemas are stable and tabular.
- Wide session files use custom validation backed by typed metadata models.
- DuckDB sits above the canonical Parquet lake and queries it directly.

## Why Wide At Session Level

Most current workflows are session- and trial-centric.

- Marker, analog, and forceplate files map naturally to biomechanics-native
  arrays.
- Trial reconstruction for OpenSim and similar tools stays straightforward.
- Session bundles remain easy to distribute as self-contained subsets.

Wide session files are the operational payload.

## Why Long At Higher Levels

Long schemas are still important.

- They are easier to validate with Patito.
- They provide a stable contract across sessions with different marker sets.
- They are easier to aggregate and query across sessions.
- They map cleanly onto the DuckDB orchestration layer.

Long schemas are the analytical contract.

## Tiered Model

### Tier 1: Session Storage

Each session stores canonical Parquet files such as:

- `markers.parquet`
- `analogs.parquet`
- `forceplates.parquet`
- `events.parquet`
- `parameters.json`

These files are intended for direct session-level workflows and preserve the
current wide/struct payloads for signals.

### Tier 2: Analytical Projections

The storage layer exposes explicit conversions and lazy scans for long-format
projections.

- markers: one row per `(trial_name, frame, marker_name)`
- analogs: one row per `(trial_name, frame, channel_name)`
- forceplates: one row per `(trial_name, frame, fp_name, variable, axis)`
- events: one row per event

These projections can be computed lazily from session files and later
materialized if needed.

### Tier 3: DuckDB Orchestration Layer

DuckDB sits above the session files and queries the Parquet lake directly at the
dataset root.

- query metadata across sessions
- expose reusable root-level views over many Parquet files at once
- join signal tables with session parameters and trial metadata
- persist rebuildable orchestration tables such as session/trial metrics and
  quality results
- serve as the primary entrypoint for notebooks and broad interactive workflows

## Validation Strategy

### Wide Files

Wide signal files are validated in layers:

1. file metadata envelope
2. required base columns (`trial_name`, `frame`, `time`)
3. dynamic signal columns vs metadata names
4. nested struct shapes for markers and forceplates
5. frame/time consistency checks

### Long Files

Long analytical tables use Patito models because they have stable row schemas.

## Current Implementation Scope

The current architecture separates canonical storage from orchestration.

- `movedb.storage` defines typed session-level Parquet contracts
- conversion writes canonical session bundles only
- DuckDB exposes root-level views over many session Parquet files
- expensive reusable selection/orchestration results can be materialized in
  DuckDB tables and refreshed from canonical Parquet
- notebooks and batch workflows start from DuckDB, then drill down into session
  Parquet only when needed for execution

See also `docs/notebook-workflows.md` for the notebook/workbench integration
pattern built on top of the DuckDB catalog.
