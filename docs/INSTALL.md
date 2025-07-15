# Installation Guide

This guide provides comprehensive installation instructions for movedb-core.

## Quick Start

### For End Users

```bash
# Recommended: Install from conda
conda install -c hudsonburke movedb-core

# Coming soon: conda-forge (v1.0.0)
# conda install -c conda-forge movedb-core
```

### For Developers

```bash
# Clone repository
git clone https://github.com/SOMA-Bionics/movedb-core.git
cd movedb-core

# Create development environment
conda env create -f environment.yml
conda activate movedb-core-dev

# Install in development mode
pip install -e .
```

## Detailed Installation Options

### Option 1: Conda Installation (Recommended)

**Why conda?** Key dependencies (`ezc3d`, `opensim`) are only available through conda.

```bash
# Install from personal channel (current)
conda install -c hudsonburke movedb-core

# Install development version
conda install -c hudsonburke -c dev movedb-core
```

### Option 2: Development Installation

#### Prerequisites

- conda or miniconda installed
- Git

#### Steps

1. **Clone the repository**:

   ```bash
   git clone https://github.com/SOMA-Bionics/movedb-core.git
   cd movedb-core
   ```

2. **Create conda environment**:

   ```bash
   conda env create -f environment.yml
   conda activate movedb-core-dev
   ```

3. **Install package in development mode**:

   ```bash
   pip install -e .
   ```

4. **Verify installation**:

   ```bash
   python -c "import movedb; print(f'movedb version: {movedb.__version__}')"
   ```

### Option 3: Manual Environment Setup

If you prefer to set up your own environment:

```bash
# Create environment
conda create -n movedb-env python=3.11

# Activate environment
conda activate movedb-env

# Install dependencies
conda install -c conda-forge numpy polars pydantic loguru ezc3d
conda install -c opensim-org opensim

# Install movedb-core
pip install movedb-core  # From PyPI (when available)
# OR
pip install -e .  # From source
```

## Verification

Test your installation:

```bash
python -c "
import movedb
from movedb.core import Trial
from movedb.file_io import C3DLoader
print('✅ movedb-core installed successfully!')
print(f'Version: {movedb.__version__}')
"
```

## Development Tools

If you're developing movedb-core:

### Install Development Dependencies

```bash
# Already included in environment.yml
conda install -c conda-forge pytest pytest-cov black isort flake8 mypy
```

### Available Commands

#### Linux/macOS (using make)

```bash
# Run tests
make test

# Code quality checks
make lint

# Build conda package
make build

# Show all commands
make help
```

#### Windows (alternatives)

**Option 1: Using our batch script**

```cmd
REM Run tests
scripts\make.bat test

REM Code quality checks
scripts\make.bat lint

REM Build conda package
scripts\make.bat build

REM Show all commands
scripts\make.bat help
```

**Option 2: Using PowerShell script**

```powershell
# Run tests
.\scripts\make.ps1 test

# Code quality checks
.\scripts\make.ps1 lint

# Build conda package
.\scripts\make.ps1 build

# Show all commands
.\scripts\make.ps1 help
```

**Option 3: Install make for Windows**

- Install via [Chocolatey](https://chocolatey.org/): `choco install make`
- Install via [Scoop](https://scoop.sh/): `scoop install make`
- Install [Git for Windows](https://gitforwindows.org/) (includes make)
- Use [Windows Subsystem for Linux (WSL)](https://docs.microsoft.com/en-us/windows/wsl/)

## Troubleshooting

### Common Issues

#### ImportError: No module named 'ezc3d'

**Solution**: Use conda installation. ezc3d is not available on PyPI.

```bash
conda install -c conda-forge ezc3d
```

#### ImportError: No module named 'opensim'

**Solution**: Install OpenSim from opensim-org channel.

```bash
conda install -c opensim-org opensim
```

#### Version conflicts

**Solution**: Use a clean conda environment.

```bash
conda create -n clean-movedb python=3.11
conda activate clean-movedb
conda install -c hudsonburke movedb-core
```

### Platform-Specific Notes

#### Windows

- Use Anaconda Prompt or PowerShell
- Some OpenSim features may require Visual C++ Redistributable
- **Make command not available**: Use our provided scripts:
  - `scripts\make.bat` (Command Prompt/PowerShell)
  - `scripts\make.ps1` (PowerShell with advanced features)
- Alternative: Install make via [Chocolatey](https://chocolatey.org/), [Scoop](https://scoop.sh/), or [Git for Windows](https://gitforwindows.org/)

#### macOS

- Works with both Intel and Apple Silicon
- May need Xcode command line tools for some dependencies

#### Linux

- Tested on Ubuntu 20.04+ and CentOS 7+
- May need system packages for graphics (if using GUI features)

## Building from Source

### Prerequisites

```bash
conda install -c conda-forge conda-build conda-verify
```

### Build Process

```bash
# Build conda package
./scripts/build_conda.sh

# Verify package
conda-verify dist/conda/**/*.conda

# Install locally built package
conda install dist/conda/**/*.conda
```

### Upload to Anaconda.org

```bash
# Install anaconda-client
conda install anaconda-client

# Upload package
anaconda upload dist/conda/**/*.conda
```

## Environment Files

### environment.yml

Complete development environment with all dependencies.

### conda-recipe/meta.yaml

Conda package recipe for building distribution packages.

## Support

- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues
- **Development**: See `docs/DEVELOPMENT.md`

## Next Steps

After installation:

1. Read the main [README.md](../README.md) for usage examples
2. Check out [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for development guidelines
3. See example notebooks in `notebooks/` directory
