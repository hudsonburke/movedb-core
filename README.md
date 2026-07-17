# MoveDB — Movement Database

Batch-import biomechanics data into [Rerun](https://rerun.io) `.rrd` files,
then visualize, catalog, and query across recordings.

```
C3D files ──┐
OSIM files ─┼──► movedb import ──► .rrd files ──► rerun server ──► Rerun Viewer
B3D files ──┘                              │                    │
                                            └──► DuckDB ──► SQL queries
```

## Quick start

```bash
# Install
pip install "movedb-core[all] @ git+https://github.com/hudsonburke/movedb-core.git"

# Import C3D files grouped by subject
movedb import c3d /data/c3d_root -o /data/rrd/

# Serve via the Rerun catalog server
movedb catalog serve /data/rrd/

# Or query with SQL directly
movedb catalog query /data/rrd/ "SELECT entity_path, value FROM scalars WHERE entity_path LIKE '%body_measurements/mass'"
```

## Why MoveDB?

Biomechanics data lives in many formats — C3D, OpenSim models and results
(.osim, .mot, .sto, .trc), AddBiomechanics (.b3d) — each with its own tools
and workflows.  MoveDB provides a single entry point to convert all of them
into a unified format that can be visualised, queried, and catalogued with
modern data science tools.

**The conversion is a one-time cost.**  Run it on an x86_64 workstation (the
only architecture with nimblephysics wheels), then the resulting `.rrd` files
work on any platform — ARM64 laptops, cloud servers, anywhere Rerun runs.

## Commands

| Command | What it does |
|---------|-------------|
| `movedb import c3d <dir> -o <out>` | Walk a directory for C3D files, group by subject, produce one `.rrd` per subject |
| `movedb import osim <dir> -o <out>` | Walk a directory for OpenSim files, produce `.rrd` files |
| `movedb import b3d <dir> -o <out>` | Walk a directory for B3D files, produce `.rrd` files (x86_64 only) |
| `movedb catalog serve <path>` | Start the Rerun catalog server pointing at a directory of `.rrd` files |
| `movedb catalog query <path> <sql>` | Query `.rrd` files with SQL using the DuckDB `rrd` extension |
| `movedb info` | Show which importers and dependencies are available |

## Architecture

```
                  ┌──────────────┐
                  │  C3D files   │──┐
                  └──────────────┘  │
                  ┌──────────────┐  │  ┌──────────────────┐  ┌──────────────┐
                  │ OpenSim files│──┼──┤ rerun-importer-* ├──┤  .rrd files  │
                  └──────────────┘  │  └──────────────────┘  └──────┬───────┘
                  ┌──────────────┐  │                               │
                  │ B3D files*  │──┘                               │
                  └──────────────┘                     ┌────────────┴────────────┐
                  * x86_64 only                        │                         │
                                                  ┌────▼────┐              ┌─────▼─────┐
                                                  │  rerun  │              │  DuckDB   │
                                                  │  server │              │  rrd ext  │
                                                  └────┬────┘              └─────┬─────┘
                                                       │                        │
                                                  ┌────▼────┐              ┌────▼─────┐
                                                  │  Rerun  │              │   SQL    │
                                                  │  Viewer │              │  queries │
                                                  └─────────┘              └──────────┘
```

### Importers

Each importer is a standalone package on `$PATH` named `rerun-importer-*`.
The Rerun Viewer discovers them automatically — drag a `.c3d` file onto the
viewer and it just works.

| Package | Format | Diagram | Dependencies | Arch |
|---------|--------|---------|--------------|------|
| [rerun-importer-c3d](https://github.com/hudsonburke/rerun-importer-c3d) | `.c3d` | Markers, force plates, analogs, events | `ezc3d` | all |
| [rerun-importer-osim](https://github.com/hudsonburke/rerun-importer-osim) | `.osim`, `.mot`, `.sto`, `.trc` | Skeleton meshes, IK/ID/CMC time series | — | all |
| [rerun-importer-b3d](https://github.com/hudsonburke/rerun-importer-b3d) | `.b3d` | Kinematics, GRF, markers, force plates | `nimblephysics` | x86_64 |

### Catalog server

The Rerun catalog server (`rr.server.Server`) indexes `.rrd` files and serves
them over HTTP.  Connect the Rerun Viewer (`rerun --connect`) to browse and
query across recordings with SQL.

### DuckDB extension

The `rrd` [DuckDB community extension](https://duckdb.org/community_extensions/list_of_extensions.html)
reads `.rrd` files directly.  Query all your recordings in one SQL statement:

```sql
SELECT subject, AVG(value) as avg_mass
FROM biomechanics.scalars
WHERE entity_path LIKE '%body_measurements/mass'
GROUP BY subject;
```

## Entity path conventions

Every importer follows the same entity path scheme so queries work
consistently across datasets:

| Path pattern | Content |
|-------------|---------|
| `{subject}/subject/body_measurements/{param}` | Static subject parameters |
| `{subject}/trials/{trial}/markers` | Per-frame marker positions |
| `{subject}/trials/{trial}/ik/{dof}` | IK joint angles |
| `{subject}/trials/{trial}/id/{dof}` | ID joint moments |
| `{subject}/trials/{trial}/kinematics/{pass}/{dof}/{field}` | Kinematics pos/vel/acc/tau |
| `{subject}/trials/{trial}/grf/{body}/{force\|cop}` | Ground reaction forces |
| `{subject}/trials/{trial}/force_plates/{fp}/{force\|moment\|cop}` | Force plate data |
| `{subject}/trials/{trial}/analogs/{channel}` | Analog time series |
| `{subject}/trials/{trial}/events/{label}` | Trial events |
| `{subject}/model/bodies/{name}/mesh` | Body geometry meshes |

## Development

```bash
git clone https://github.com/hudsonburke/movedb-core.git
cd movedb-core
uv venv
uv pip install -e ".[all]"
movedb --help
```

## License

MIT
