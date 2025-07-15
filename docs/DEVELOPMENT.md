# Developer Setup Guide

## Quick Start for Testing

### 1. Create and Activate Development Environment

```bash
# Clone the repository
git clone https://github.com/SOMA-Bionics/movedb-core.git
cd movedb-core

# Create conda environment with all testing dependencies
conda env create -f environment.yml
conda activate movedb-core-dev

# OR use any conda environment with the required dependencies
conda create -n my-movedb-env python=3.11
conda activate my-movedb-env
conda install -c conda-forge -c opensim-org pytest pytest-cov black flake8 mypy numpy polars pydantic ezc3d numpydantic pandera-polars
```

### 2. Install Package in Development Mode

```bash
pip install -e .
```

### 3. Run Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src/movedb --cov-report=html

# Run specific test file
pytest tests/test_basic.py -v

# Run tests with verbose output
pytest -v

# Run tests and stop on first failure
pytest -x

# Run tests matching a pattern
pytest -k "test_trial" -v
```

### 4. Common Test Commands

```bash
# Quick test run (no coverage)
pytest --no-cov

# Test with coverage and open HTML report
pytest --cov=src/movedb --cov-report=html && open htmlcov/index.html

# Test specific functionality
pytest tests/test_basic.py::test_trial_creation -v

# Run tests in parallel (if pytest-xdist is installed)
pytest -n auto
```

## Code Quality and Linting

### 5. Run Linting Checks

The project uses several tools to maintain code quality:

```bash
# Run all linting checks (like CI)
make lint

# Auto-fix formatting and import issues
make lint-fix

# Individual linting tools
make flake8      # Check code style
make mypy        # Type checking
make format      # Format with black
make isort       # Sort imports

# Check without fixing
make format-check  # Check black formatting
make isort-check   # Check import sorting
```

### Linting Tools Used

- **Black**: Code formatter (127 char line length)
- **isort**: Import sorter (Black-compatible profile)
- **flake8**: Code style linter (ignores E203 for Black compatibility)
- **mypy**: Static type checker

### Pre-commit Workflow

```bash
# Before committing, run:
make pre-commit  # This runs linting + quick tests

# Or step by step:
make lint-fix    # Fix formatting issues
make test-quick  # Run tests without coverage
```

### Configuration Files

- `setup.cfg` - flake8 configuration
- `pyproject.toml` - black, isort, mypy, pytest configuration

## Testing Best Practices

### Import Style for Tests

Use explicit submodule imports in tests:

```python
# Recommended for tests
from movedb.core import Trial, Event, Points, Analogs
from movedb.file_io import C3DLoader, OpenSimExporter

# Instead of flat imports
from movedb import Trial, Event  # Still works but less clear
```

### Test File Organization

- `tests/test_basic.py` - Basic functionality and imports
- `tests/test_core/` - Core functionality tests
- `tests/test_file_io/` - File I/O tests
- `tests/test_integration/` - Integration tests

### Writing Tests

```python
import pytest
from movedb.core import Trial, Event

def test_example():
    """Test description."""
    # Test implementation
    pass

def test_example_with_fixtures():
    """Test with fixtures."""
    # Use fixtures for common setup
    pass
```

## CI/CD Integration

Tests and linting are automatically run on:

- Pull requests
- Push to main branch
- Release creation

### Conda Package Distribution

The CI/CD workflow automatically builds and uploads conda packages:

- **Tagged releases** (e.g., `v1.0.0`): Uploaded to main channel
- **Main branch pushes**: Uploaded to development channel (`--label dev`)

See [CONDA_PACKAGING.md](CONDA_PACKAGING.md) for detailed information.

## Makefile Commands

For convenience, common development tasks are available via `make`:

```bash
# Environment setup
make install      # Install package in development mode
make install-dev  # Create conda environment and install
make update-env   # Update conda environment

# Testing
make test         # Run all tests with coverage
make test-quick   # Run tests without coverage (faster)
make test-verbose # Run tests with verbose output

# Code quality
make lint         # Run all linting checks
make lint-fix     # Auto-fix formatting and imports
make pre-commit   # Run checks before committing
make ci-check     # Run CI checks locally

# Building
make build        # Build conda package
make validate     # Validate package installation

# Version management
make bump-patch   # Bump patch version
make bump-minor   # Bump minor version
make bump-major   # Bump major version

# Development workflows
make dev-setup    # Full development setup
make dev-test     # Format, lint, and test
make clean        # Clean build artifacts
```

Run `make help` to see all available commands.

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure package is installed with `pip install -e .`
2. **Missing dependencies**: Run `conda env update -f environment.yml` or install required packages
3. **Test failures**: Check that you're in a conda environment with pytest installed
4. **Environment name**: The test runner works with any conda environment that has the required dependencies

### Environment Issues

```bash
# Recreate environment if needed
conda env remove -n movedb-core-dev  # or your environment name
conda env create -f environment.yml
conda activate movedb-core-dev        # or your environment name
pip install -e .

make clean-conda   # Clean conda build artifacts
make upload-conda  # Upload conda package to Anaconda.org
make build-upload  # Build and upload conda package

# OR install dependencies in existing environment
conda install -c conda-forge -c opensim-org pytest pytest-cov
pip install -e .
```

### Coverage Issues

If coverage isn't working:

```bash
# Install coverage dependencies
conda install pytest-cov coverage
```

## VSCode Integration

Add to your VSCode `settings.json`:

```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ],
    "python.testing.unittestEnabled": false,
    "python.testing.cwd": "${workspaceFolder}",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black"
}
```
