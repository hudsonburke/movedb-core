# MoveDB Core

<img src="imgs/MoveDB-Logo-nobg-cropped.png" width="40%">

[![Tests](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/tests.yml/badge.svg)](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/tests.yml)
[![CI/CD](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/ci-cd.yml)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Core library for movement-data ingestion, typed biomechanics models, and
Parquet-based storage workflows.

## Current Focus

MoveDB is moving toward a Parquet-first architecture.

- ingest trial data from formats like C3D
- represent signals with typed Pydantic models
- serialize session bundles to Polars/Parquet
- support both session-level processing and higher-level analytical workflows
- prepare for a later DuckDB catalog/query layer

## Storage Direction

The current implementation plan uses a tiered model.

- session motion files remain canonical in wide/struct form
- long/row-oriented projections provide a stable analytical contract
- Patito is used for fixed tabular schemas
- wide session files use custom validation backed by typed metadata models

See `docs/storage-architecture.md` for the working design.

## Core Capabilities

- **C3D ingestion**: Parse markers, analogs, forceplates, and events
- **Typed models**: Pydantic domain models for signal metadata and trial data
- **Polars adapters**: Convert core models to wide and long DataFrames
- **Parquet storage**: Write self-describing Parquet files with embedded metadata
- **Session workflows**: Support per-session bundles for subset distribution

## Near-Term Plan

The next implementation phase focuses on the storage layer before DuckDB.

- add a dedicated `movedb.storage` package
- define Patito-backed schemas for stable tabular contracts
- add explicit read, write, and lazy scan functions for Parquet files
- add wide-file validators for session-level signal payloads

## License

MIT License - see [LICENSE](LICENSE) file for details.
