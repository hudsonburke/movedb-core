# MoveDB Workflow Guide

End-to-end guide for taking raw biomechanics data to interactive Rerun
visualizations and cross-recording SQL queries.

---

## 1. Install the tools

On your **conversion workstation** (x86_64 recommended for B3D support):

```bash
pip install "movedb-core[all] @ git+https://github.com/hudsonburke/movedb-core.git"
```

This installs:
- `movedb` CLI
- All three importers: `rerun-importer-c3d`, `rerun-importer-osim`, `rerun-importer-b3d`
- `rerun-sdk` for the catalog server
- `duckdb` for SQL queries

Check everything is available:

```bash
movedb info
```

On **ARM64 machines** (M-series Macs, Linux ARM servers), install without the
b3d extras:

```bash
pip install "movedb-core[c3d,osim] @ git+https://github.com/hudsonburke/movedb-core.git"
```

> The `.rrd` files produced by conversion are **architecture-independent**.
> Convert on x86_64 once, then copy the `.rrd` files to any machine.

---

## 2. Organise your data

MoveDB's batch importers recursively scan directories and group files by
subject.  Recommended layout:

```
data/
├── c3d/
│   ├── subject_001/
│   │   ├── walk_01.c3d
│   │   └── walk_02.c3d
│   └── subject_002/
│       ├── run_01.c3d
│       └── squat_01.c3d
├── opensim/
│   └── RajagopalData/
│       ├── Rajagopal2015.osim
│       ├── IK/results_walk/ik_output_walk.mot
│       ├── ID/results_walk/inverse_dynamics.sto
│       └── ...
└── b3d/
    ├── subject_a.b3d
    └── subject_b.b3d
```

---

## 3. Convert to `.rrd`

### C3D files

```bash
movedb import c3d data/c3d -o output/rrd
```

This:
1. Scans recursively for all `.c3d` files
2. Reads each file's `SUBJECTS/NAMES` parameter to group by subject
3. Extracts body measurements (`PROCESSING` params) once per subject
4. Produces one `.rrd` file per subject

### OpenSim files

```bash
movedb import osim data/opensim -o output/rrd
```

Produces one `.rrd` per model/results group.  Animate with IK data:

```bash
rerun-importer-osim Rajagopal2015.osim --animate IK/results_walk/ik_output_walk.mot
```

### B3D files

```bash
movedb import b3d data/b3d -o output/rrd
```

Each `.b3d` file contains one subject with multiple trials and processing
passes (kinematics, dynamics, etc.).

---

## 4. Visualize

### Single file

```bash
rerun output/rrd/subject_001.rrd
```

### Browse the catalog

```bash
# Start the catalog server
movedb catalog serve output/rrd/ --port 51234

# In another terminal, connect the viewer
rerun --connect rerun+http://localhost:51234/proxy
```

The viewer shows all subjects and trials in the dataset.  Use the blueprint
panel to switch between 3D views, scalar plots, and the SQL query panel.

---

## 5. Query across recordings

### With the DuckDB extension

```bash
# List all subjects and their mass
movedb catalog query output/rrd/ \
  "SELECT entity_path, value FROM biomechanics.scalars WHERE entity_path LIKE '%body_measurements/mass'"

# Find subjects above a mass threshold
movedb catalog query output/rrd/ --format json \
  "SELECT entity_path, value FROM biomechanics.scalars WHERE entity_path LIKE '%body_measurements/mass' AND value > 70"
```

### With the Python SDK

```python
import rerun as rr
client = rr.catalog.CatalogClient("rerun+http://localhost:51234")
dataset = client.get_dataset("biomechanics")
view = dataset.filter_contents(
    rr.catalog.ContentFilter.everything()
    .include("/**/body_measurements/**")
)
arrow_tables = view.reader().read_all()
# arrow_tables is a list of PyArrow tables
```

---

## 6. Platform limitations

| Importer | Architecture | Reason |
|----------|-------------|--------|
| `rerun-importer-c3d` | all | Pure Python + ezc3d with ARM64 wheels |
| `rerun-importer-osim` | all | Pure Python XML parsing |
| `rerun-importer-b3d` | x86_64 | Requires nimblephysics (no ARM64 wheel) |

The conversion from B3D files must be done on an x86_64 machine.  The
resulting `.rrd` files work on any architecture.

Once OpenSim and nimblephysics ship `manylinux_aarch64` wheels, all importers
will work everywhere.

---

## 7. Tips

- **Body measurements**: The C3D importer extracts `PROCESSING` parameters
  (mass, segment lengths, COMs) once and logs them as static scalars.  Query
  them with `WHERE entity_path LIKE '%/body_measurements/%'`.
- **Batch speed**: For large datasets, the batch importer processes files
  sequentially.  Hundreds of C3D files take a few minutes.
- **Test first**: Run `rerun-importer-c3d single_file.c3d` to test a single
  file before batch importing a whole directory.
- **DuckDB**: Install the `rrd` extension once: `pip install duckdb` and the
  extension loads automatically via `INSTALL rrd FROM community`.
