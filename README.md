# MoveDB Core

<img src="imgs/MoveDB-Logo-nobg-cropped.png" width="40%">

[![Tests](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/tests.yml/badge.svg)](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/tests.yml)
[![CI/CD](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/ci-cd.yml)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Core library for movement-data ingestion, typed biomechanics models, Parquet-
based storage workflows, and DuckDB-backed dataset orchestration.

## Current Focus

MoveDB uses a Parquet-first architecture with DuckDB as the dataset-level
query and orchestration layer.

- ingest trial data from formats like C3D
- represent signals with typed Pydantic models
- serialize session bundles to Polars/Parquet
- support both session-level processing and higher-level analytical workflows
- expose dataset-level DuckDB views over canonical Parquet bundles
- support notebook and workflow orchestration on top of the catalog

## Storage Direction

The current implementation plan uses a tiered model.

- session motion files remain canonical in wide/struct form
- long/row-oriented projections provide a stable analytical contract
- Patito is used for fixed tabular schemas
- wide session files use custom validation backed by typed metadata models

See `docs/storage-architecture.md` for the working design and
`docs/notebook-workflows.md` for the notebook/workbench integration pattern.

## Core Capabilities

- **C3D ingestion**: Parse markers, analogs, forceplates, and events
- **Typed models**: Pydantic domain models for signal metadata and trial data
- **Polars adapters**: Convert core models to wide and long DataFrames
- **Parquet storage**: Write self-describing Parquet files with embedded metadata
- **Session workflows**: Support per-session bundles for subset distribution
- **DuckDB catalog**: Query many canonical Parquet files directly at the dataset root
- **Notebook helpers**: Support DuckDB-first interactive workflow selection and scratch inspection

## Current Architecture

The current implementation separates canonical storage from orchestration.

- `movedb.storage` defines typed session-level Parquet contracts
- session bundles remain the canonical operational payload
- `movedb.catalog` exposes root-level DuckDB views over the Parquet lake
- derived metrics and quality tables can be materialized in DuckDB and refreshed
  from canonical Parquet
- notebook and batch workflows begin at the DuckDB layer and drill into
  session bundles only when needed

## License

MIT License - see [LICENSE](LICENSE) file for details.
