# MoveDB Core

<img src="imgs/MoveDB-Logo-nobg-cropped.png" width="40%">

[![Tests](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/tests.yml/badge.svg)](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/tests.yml)
[![CI/CD](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/ci-cd.yml)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Core library for movement database operations, including C3D file I/O and OpenSim integration.

## Features

- **C3D File I/O**: Read and process C3D motion capture files
- **OpenSim Integration**: Export data to OpenSim formats (TRC, MOT, XML)
- **Time Series Processing**: Handle marker trajectories and analog data
- **Force Platform Support**: Process force platform data from C3D files
- **Data Validation**: Built-in data validation with numpydantic and pandera-polars
- **Type Safety**: Full type hints and Pydantic models for data integrity

## Installation

### From Conda (Recommended)

```bash
# Currently available from personal channel
conda install -c hudsonburke movedb-core

# Coming soon: conda-forge (planned for v1.0.0)
# conda install -c conda-forge movedb-core
```

**Note**: We strongly recommend using conda, as `opensim` is not available on PyPI.

### From PyPI (Limited Support)

```bash
# Install core package (OpenSim features will be disabled)
pip install movedb-core

# To use OpenSim features, install OpenSim separately via conda:
# Note: OpenSim requires Python 3.7-3.12 (not 3.13+)
conda install -c opensim-org opensim
```

⚠️ **Important**:

- OpenSim is not available on PyPI and must be installed via conda
- OpenSim only supports Python 3.7-3.12 (not compatible with Python 3.13+)
- If you're using Python 3.13+, you'll need a separate environment for OpenSim features

### From Source

```bash
git clone https://github.com/SOMA-Bionics/movedb-core.git
cd movedb-core

# Using conda for dependencies (REQUIRED)
conda env create -f environment.yml
conda activate movedb-core-dev
pip install -e .
```

### OpenSim with Python 3.13+

If you're using Python 3.13 or later, OpenSim is not compatible. You have two options:

**Option 1: Separate Environment for OpenSim Features**

```bash
# Quick setup using our OpenSim environment file:
conda env create -f environment-opensim.yml
conda activate movedb-opensim

# Or manually:
conda create -n movedb-opensim python=3.12
conda activate movedb-opensim
pip install movedb-core
conda install -c opensim-org opensim

# Or use our setup script:
./scripts/setup_opensim_env.sh

# Use your main Python 3.13+ environment for non-OpenSim work
conda activate your-main-env
pip install movedb-core  # OpenSim features will be disabled
```

**Option 2: Use movedb-core without OpenSim**

```bash
# Install in your Python 3.13+ environment
pip install movedb-core
# All features work except OpenSim export (TRC, MOT, XML)
```

**Testing Your Setup**

```bash
# Test your installation and check OpenSim availability:
python examples/opensim_example.py
```

For detailed installation instructions, see [docs/INSTALL.md](docs/INSTALL.md).

## Documentation

📚 **Complete documentation is available in [docs/README.md](docs/README.md)**, including:

- Installation guide and development setup
- API design and architecture
- Testing and code quality guidelines  
- CI/CD and packaging workflows
- Version 1.0.0 roadmap

📝 **[CHANGELOG.md](CHANGELOG.md)** - Track all changes and updates to the project

## Quick Start

```python
from movedb.core import Trial

# Load a C3D file
trial = Trial.from_c3d_file("path/to/your/file.c3d")

# Access marker data
markers = trial.points.trajectories
print(f"Loaded {len(markers)} markers")

# Access force platform data
if trial.force_platforms:
    print(f"Found {len(trial.force_platforms)} force platforms")

# Export to OpenSim TRC format
trial.to_trc("output.trc")

# Run OpenSim Inverse Kinematics
trial.run_opensim_ik("model.osim", output_dir="ik_results")
```

## API Structure

The `movedb` package is organized into logical submodules for clear separation of concerns:

- `movedb.core`: Core data structures and classes
- `movedb.file_io`: File input/output functionality
- `movedb.utils`: Utility functions

You can import classes using explicit submodule imports:

```python
from movedb.core import Trial, Event, Points, Analogs
from movedb.file_io import C3DLoader, OpenSimExporter
```

This approach provides clear API structure and supports future expansion (e.g., `from movedb.api import TrialDB`).

## Development

### Quick Development Setup

```bash
# Clone and set up environment
git clone https://github.com/SOMA-Bionics/movedb-core.git
cd movedb-core
conda env create -f environment.yml
conda activate movedb-core-dev
pip install -e .
```

### Running Tests

```bash
# Quick test run
make test-quick

# Full test suite with coverage
make test

# Run specific test file
make test-specific FILE=test_basic.py

# Run tests matching pattern
make test-pattern PATTERN=trial

# Alternative: use Python runner
python scripts/run_tests.py
```

### Code Quality

```bash
# Run all linting checks (like CI)
make lint

# Auto-fix formatting and import issues
make lint-fix

# Pre-commit checks (lint + test)
make pre-commit
```

### Available Make Commands

- `make test` - Run all tests with coverage
- `make test-quick` - Run tests without coverage (faster)
- `make lint` - Run all linting checks (black, isort, flake8, mypy)
- `make lint-fix` - Auto-fix formatting and import sorting
- `make format` - Format code with black
- `make build` - Build conda package
- `make clean` - Clean build artifacts
- `make help` - Show all available commands

For detailed information about individual scripts, see [`scripts/README.md`](scripts/README.md).

See [`docs/README.md`](docs/README.md) for a complete documentation index, including detailed development guidelines and setup information.

## Core Classes

- `Trial`: Main container for motion capture trial data
- `Points`: Marker trajectory data with gap detection
- `Analogs`: Analog channel data (EMG, force platforms, etc.)
- `Event`: Trial events with timing information
- `EZC3DForcePlatform`: Force platform data container based on ezc3d's force platform filter

## Requirements

- Python 3.8+ (3.8-3.12 recommended for OpenSim compatibility)
- numpy >= 1.20.0
- polars >= 0.20.0
- pydantic >= 2.0.0
- numpydantic >= 1.0.0 *(for data validation)*
- pandera-polars >= 0.20.0 *(for data validation)*
- ezc3d >= 1.5.0

### Optional Dependencies

- opensim >= 4.0.0 *(available via conda only)*
  - Required for OpenSim export features (TRC, MOT, XML)
  - **Python compatibility**: OpenSim supports Python 3.7-3.12 (not 3.13+)
  - Install with: `conda install -c opensim-org opensim`
  - If using Python 3.13+, create a separate environment with Python ≤3.12

## Development

```bash
# Clone the repository
git clone https://github.com/SOMA-Bionics/movedb-core.git
cd movedb-core

# Create conda environment with dependencies (REQUIRED)
conda env create -f environment.yml
conda activate movedb-core-dev
pip install -e ".[dev]"

# Alternative: Manual setup
conda create -n movedb-dev python=3.11
conda activate movedb-dev
conda install -c conda-forge numpy polars pydantic ezc3d numpydantic pandera-polars
pip install -e ".[dev]"
```

### Building and Packaging

Build conda package locally:

```bash
# Install build dependencies
conda install -c conda-forge conda-build conda-verify

# Build package
./scripts/build_conda.sh

# Verify package
conda-verify dist/conda/**/*.conda
```

The CI/CD workflow automatically builds and uploads conda packages to Anaconda.org:

- **Tagged releases** (e.g., `v1.0.0`) → Main channel
- **Main branch pushes** → Development channel (`--label dev`)

For conda-forge submission (to make the package available as `conda install -c conda-forge movedb-core`), see [docs/CONDA_FORGE_SUBMISSION.md](docs/CONDA_FORGE_SUBMISSION.md).

### Version 1.0.0 Roadmap

We're working toward a stable v1.0.0 release for conda-forge submission. Track our progress:

```bash
# Check readiness for v1.0.0
make check-v1-readiness
```

See [docs/ROADMAP_V1.md](docs/ROADMAP_V1.md) for the complete roadmap and timeline.

For more details, see [docs/CONDA_PACKAGING.md](docs/CONDA_PACKAGING.md).

### Testing and Quality

Run tests:

```bash
pytest
```

Run linting and formatting:

```bash
make lint        # Check code quality
make lint-fix    # Fix formatting issues
make pre-commit  # Run pre-commit checks
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
