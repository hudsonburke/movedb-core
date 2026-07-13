# Notebook Workflows

MoveDB provides a DuckDB-first pattern for interactive notebook workflows.

The intended split is:

- canonical data stays in per-session Parquet bundles
- DuckDB serves as the dataset-level orchestration and query layer
- project notebooks execute domain-specific workflows and write experimental
  outputs to scratch locations

## Core Pattern

Interactive workflows should start from a root-level DuckDB catalog.

- use DuckDB to list subjects, sessions, and trials
- use DuckDB to inspect qualification state and metadata
- use DuckDB temp views to register scratch outputs during a notebook session
- load canonical Parquet directly only when running a session- or trial-local
  computation

This keeps notebook selection and diagnostics fast while preserving canonical
session bundles as the source of truth.

## Catalog Helpers

MoveDB exposes generic notebook helpers in `movedb.catalog`:

- `connect_workbench_catalog(...)`
- `sql_list_subjects(...)`
- `sql_list_sessions(...)`
- `sql_list_trials(...)`
- `register_scratch_views(...)`
- `sql_compare_canonical_vs_scratch(...)`
- `sql_current_view_preview(...)`

These helpers are intended to support project-specific notebook apps without
duplicating DuckDB query utilities across repositories.

## Typical Project Integration

A project repository should usually keep three layers distinct.

### 1. MoveDB Core

- storage contracts
- catalog registry and views
- generic DuckDB notebook/query helpers

### 2. Project Workflow Layer

- domain-specific qualification logic
- project-specific execution helpers
- project parameter models

### 3. Notebook UI Layer

- widgets and selection UX
- scratch execution controls
- domain-specific plotting

## Scratch Outputs

Notebook experiments should write to scratch space rather than canonical
session `opensim/` or equivalent analysis directories.

Recommended pattern:

- scratch root is separate from canonical bundles
- scratch outputs are registered into DuckDB temp views
- notebooks compare canonical metadata with scratch outputs in one session

## Why This Pattern Works

- broad queries stay efficient because DuckDB scans the Parquet lake directly
- notebooks stay reactive and query-driven
- session bundles remain canonical and portable
- project repositories can build domain-specific workbenches without forking
  core catalog logic

## Example Responsibilities

What belongs in MoveDB:

- dataset-root Parquet views in DuckDB
- generic session/trial listing helpers
- scratch-view registration and preview helpers

What stays in project repositories:

- OpenSim execution logic
- gait qualification rules
- project parameter semantics
- plotting defaults and notebook UX
