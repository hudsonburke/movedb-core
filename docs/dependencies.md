# Dependencies & Formats

MoveDB is built on a small set of well-supported open-source tools. This
document provides a brief introduction to each, explains why MoveDB uses it,
and links to the official documentation.

## Apache Parquet

[Parquet](https://parquet.apache.org/) is a columnar storage format designed
for efficient analytical queries. Unlike row-based formats (CSV, HDF5),
Parquet stores data by column, which means queries that read a subset of
columns skip the rest entirely.

**Why MoveDB uses it:**

- **Columnar layout** is a natural fit for biomechanics signals where
  workflows typically access a few channels out of many.
- **Self-describing** — Parquet files embed their schema and metadata, so
  there are no sidecar schema files to keep in sync.
- **Efficient compression** — columnar storage compresses far better than
  row-based formats because similar values are adjacent. Typical compression
  ratios for motion capture data are 3–10x over raw CSV.
- **Portable** — Parquet is an open standard supported by virtually every
  data tool: Python, R, Spark, DuckDB, Polars, pandas, and more.
- **Immutable** — once written, a Parquet file is a stable artifact. This
  makes session bundles easy to version, distribute, and cache.

**Useful packages:**

| Package | Purpose |
|---|---|
| [Polars](https://pola.rs/) | Fast DataFrame library with native Parquet read/write |
| [PyArrow](https://arrow.apache.org/docs/python/) | Apache Arrow bindings; low-level Parquet access |
| [DuckDB](https://duckdb.org/) | Query Parquet files directly with SQL, no import step |

**Learn more:** [Parquet docs](https://parquet.apache.org/docs/),
[Parquet format specification](https://parquet.apache.org/docs/file-format/)

## DuckDB

[DuckDB](https://duckdb.org/) is an in-process analytical database — think
SQLite but optimized for analytical queries (aggregations, joins, scans) rather
than transactional workloads. It runs inside your application with no separate
server process.

**Why MoveDB uses it:**

- **Reads Parquet directly** — `SELECT * FROM read_parquet('data/*.parquet')`
  works without importing files into a database. This means DuckDB can query
  the entire Parquet lake at a dataset root with zero ETL.
- **Fast aggregations** — columnar execution engine optimized for the exact
  patterns biomechanics workflows need (group-by DOF, filter by subject,
  compute summary statistics).
- **Zero deployment** — no server, no configuration, no port management.
  A Python import and a file path is all you need.
- **SQL interface** — researchers who know SQL can query their data
  immediately without learning a new API.

**Useful packages:**

| Package | Purpose |
|---|---|
| [duckdb Python](https://duckdb.org/docs/api/python/overview) | Official Python bindings |
| [duckdb-wasm](https://duckdb.org/docs/api/wasm) | Run DuckDB in the browser via WebAssembly |

**Learn more:** [DuckDB docs](https://duckdb.org/docs/),
[DuckDB Python API](https://duckdb.org/docs/api/python/overview)

## Polars

[Polars](https://pola.rs/) is a DataFrame library written in Rust, designed
as a modern alternative to pandas. It uses Apache Arrow as its in-memory
format and supports lazy evaluation — you describe a query, and Polars
optimizes and executes it only when you need the results.

**Why MoveDB uses it:**

- **Performance** — Polars is significantly faster than pandas for the
  large, structured datasets common in biomechanics.
- **Native Parquet** — `pl.read_parquet()` and `df.write_parquet()` are
  first-class operations, not bolted-on I/O.
- **Lazy evaluation** — scan a Parquet file without loading it into memory,
  then execute only the columns and rows you need.
- **Type safety** — Polars enforces column types strictly, which pairs well
  with Pydantic model validation.

**Learn more:** [Polars docs](https://docs.pola.rs/),
[Polars user guide](https://docs.pola.rs/user-guide/)

## Pydantic

[Pydantic](https://docs.pydantic.dev/) is a data validation library that
uses Python type annotations to define schemas. You declare a model as a
class with typed fields, and Pydantic validates, serializes, and documents
it automatically.

**Why MoveDB uses it:**

- **Domain models** — `MarkerData`, `TrialData`, `SubjectMetadata`, and
  other core types are Pydantic models with validated fields and docstrings.
- **Serialization** — `.model_dump()` and `.model_dump_json()` make it
  trivial to convert models to dicts, JSON, or Parquet-compatible structures.
- **Nested validation** — biomechanics data is hierarchical (subjects contain
  trials contain signals). Pydantic validates the entire tree.
- **IDE support** — type annotations give autocompletion and static analysis
  for free.

**Learn more:** [Pydantic docs](https://docs.pydantic.dev/),
[Pydantic v2 migration guide](https://docs.pydantic.dev/latest/migration/)

## Patito

[Patito](https://github.com/JakobGM/patito) is a schema validation library
built on top of Polars and Pydantic. It lets you define a Pydantic-style
model and validate a Polars DataFrame against it — checking column names,
types, uniqueness, nullable constraints, and custom rules.

**Why MoveDB uses it:**

- **Tabular contracts** — long-format analytical tables (one row per
  trial/DOF/frame) have stable schemas. Patito enforces them at write time.
- **Polars-native** — validates DataFrames directly, no conversion to pandas.
- **Pydantic-compatible** — uses the same model syntax, so storage-layer
  schemas feel consistent with the core domain models.

**Learn more:** [Patito docs](https://github.com/JakobGM/patito#readme)

## ezc3d

[ezc3d](https://github.com/pyomeca/ezc3d) is a Python library for reading
and writing C3D files — the standard binary format for motion capture data.
C3D files contain 3D marker trajectories, analog signals (EMG, force plates),
and event labels.

**Why MoveDB uses it:**

- **C3D is the lingua franca** of motion capture. Virtually every motion
  capture system (Vicon, Qualisys, OptiTrack, etc.) can export C3D files.
- **Lightweight** — ezc3d reads C3D files without the overhead of a full
  biomechanics toolkit like OpenSim.
- **Cross-platform** — pure Python bindings over a C++ core, works on Linux,
  macOS, and Windows.

**Learn more:** [ezc3d docs](https://pyomeca.github.io/ezc3d/),
[C3D file format](https://www.c3d.org/)

## NumPy + numpydantic

[NumPy](https://numpy.org/) is the foundational array library for Python.
[numpydantic](https://github.com/patrick-kidger/numpydantic) extends Pydantic
to validate NumPy array shapes and dtypes, so you can declare fields like
`MarkerData.positions: np.ndarray` with shape constraints in your Pydantic
models.

**Why MoveDB uses it:**

- **Signal storage** — biomechanics signals (marker trajectories, force
  plate readings, analog channels) are naturally multi-dimensional arrays.
- **Shape validation** — numpydantic ensures arrays have the expected shape
  (e.g., `(n_frames, n_markers, 3)`) at model construction time, catching
  dimension mismatches early.

**Learn more:** [NumPy docs](https://numpy.org/doc/),
[numpydantic docs](https://github.com/patrick-kidger/numpydantic#readme)

## NimblePhysics

[NimblePhysics](https://github.com/keenon/nimblephysics) (nimble) is a
differentiable physics engine for biomechanics. MoveDB uses its Python
bindings to read `.b3d` files — the AddBiomechanics binary format that
bundles subject metadata, skeleton models, trial kinematics, ground reaction
forces, and marker data into a single file.

**Why MoveDB uses it:**

- **AddBiomechanics integration** — `.b3d` files are the native format of
  the AddBiomechanics dataset, a large public collection of human movement
  data. Nimble is the canonical reader.
- **Rich metadata** — b3d files contain skeleton DOF names, body names,
  processing pass history, and quality flags that go beyond raw signals.
- **Trial-level access** — `SubjectOnDisk` provides per-trial,
  per-processing-pass access to kinematics, GRF, and marker data without
  loading the entire file.

**Note:** nimblephysics currently requires Python 3.9 for its pre-built
wheels. MoveDB's ingestion scripts run in a separate Python 3.9 environment;
the rest of MoveDB uses Python 3.12+.

**Learn more:** [NimblePhysics repo](https://github.com/keenon/nimblephysics),
[Nimble documentation](https://nimblephysics.org/)

## PyYAML

[PyYAML](https://pyyaml.org/) is a YAML parser and emitter for Python.
MoveDB uses it for configuration files (session parameters, pipeline
settings) where human readability matters more than the strictness of JSON.

**Learn more:** [PyYAML docs](https://pyyaml.org/wiki/PyYAMLDocumentation)
