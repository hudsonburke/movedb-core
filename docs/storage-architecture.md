# Storage Architecture

MoveDB is moving to a Parquet-first architecture.

The near-term goal is to make the Polars/Parquet layer explicit, typed, and
stable before adding DuckDB as a catalog/query layer.

## Direction

- Canonical session motion files stay in wide/struct form.
- Analytical projections use long/row-oriented schemas.
- Patito is used where schemas are stable and tabular.
- Wide session files use custom validation backed by typed metadata models.
- DuckDB comes later as a catalog and cross-session query layer.

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
- They will map cleanly onto the later DuckDB layer.

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

### Tier 3: DuckDB Catalog

Once the storage contract stabilizes, DuckDB will sit above the session files.

- query metadata across sessions
- expose reusable analytical views
- join long-form signal projections with session parameters and trial metadata

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

## Initial Implementation Scope

The first implementation phase focuses on the storage layer.

- add `movedb.storage`
- define Patito models for long/event/base schemas
- add typed Parquet read/write/scan helpers
- add custom wide validators for session files
- keep existing core ingest models unchanged

DuckDB work begins after these contracts settle.
