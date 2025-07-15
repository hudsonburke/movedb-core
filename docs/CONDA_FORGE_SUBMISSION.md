# Conda-forge Submission Guide for movedb-core

This guide walks through the process of submitting movedb-core to conda-forge, making it available via `conda install -c conda-forge movedb-core`.

## Overview

Conda-forge is a community-driven collection of conda recipes. Getting your package accepted involves:

1. **Preparation** - Ensure your package meets requirements
2. **Recipe Creation** - Adapt your conda recipe for conda-forge standards
3. **Submission** - Submit via staged-recipes repository
4. **Review Process** - Community review and feedback
5. **Maintenance** - Ongoing package maintenance

## Prerequisites Checklist

✅ **Package Requirements**:

- [x] Open source license (MIT ✓)
- [x] Public repository on GitHub ✓
- [x] Stable API and documentation ✓
- [x] Working conda recipe ✓
- [x] CI/CD with tests ✓
- [x] Clear license file ✓

✅ **Technical Requirements**:

- [x] Works on multiple platforms (noarch: python ✓)
- [x] Well-defined dependencies ✓
- [x] Proper version management ✓
- [x] Test suite ✓

## Step 1: Prepare Your Package

### 1.1 Ensure Package Stability

Your package should be in a reasonably stable state:

- ✅ Version 0.1.3+ (good starting point)
- ✅ Working CI/CD
- ✅ Documentation
- ✅ Test coverage

### 1.2 Review Dependencies

All dependencies must be available on conda-forge or other conda channels:

- ✅ `python`, `numpy`, `polars`, `pydantic` - Available on conda-forge
- ✅ `ezc3d` - Available on conda-forge
- ✅ `opensim` - Available on opensim-org channel (acceptable)

### 1.3 Prepare Release

Create a proper release on GitHub:

```bash
# Bump to a stable version
make bump-version VERSION=1.0.0
git push origin v1.0.0
```

## Step 2: Create Conda-forge Recipe

### 2.1 Fork staged-recipes Repository

1. Go to <https://github.com/conda-forge/staged-recipes>
2. Fork the repository to your GitHub account
3. Clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/staged-recipes.git
cd staged-recipes
```

### 2.2 Create Recipe Directory

```bash
# Create recipe directory
mkdir recipes/movedb-core
cd recipes/movedb-core
```

### 2.3 Adapt meta.yaml for Conda-forge

Create `meta.yaml` based on your current recipe but adapted for conda-forge standards:

```yaml
{% set name = "movedb-core" %}
{% set version = "1.0.0" %}

package:
  name: {{ name|lower }}
  version: {{ version }}

source:
  url: https://pypi.io/packages/source/{{ name[0] }}/{{ name }}/movedb_core-{{ version }}.tar.gz
  sha256: <SHA256_HASH_OF_PYPI_PACKAGE>
  # Alternative if not on PyPI yet:
  # url: https://github.com/SOMA-Bionics/movedb-core/archive/v{{ version }}.tar.gz
  # sha256: <SHA256_HASH_OF_GITHUB_RELEASE>

build:
  number: 0
  noarch: python
  script: {{ PYTHON }} -m pip install . -vv
  entry_points:
    # Add any console scripts here if you have them

requirements:
  host:
    - python >=3.8
    - pip
    - hatchling
  run:
    - python >=3.8
    - numpy >=1.20.0
    - polars >=0.20.0
    - pydantic >=2.0.0
    - ezc3d >=1.5.0
    - opensim  # Note: conda-forge uses 'opensim' not 'opensim-org::opensim'

test:
  imports:
    - movedb
    - movedb.core
    - movedb.file_io
    - movedb.utils
  commands:
    - python -c "import movedb; print('movedb version:', movedb.__version__)"
  requires:
    - pytest  # If you want to run tests during build

about:
  home: https://github.com/SOMA-Bionics/movedb-core
  license: MIT
  license_family: MIT
  license_file: LICENSE
  summary: Core library for movement database operations
  description: |
    MoveDB Core is a Python library for handling movement/biomechanics data including:
    - C3D file I/O operations
    - OpenSim integration  
    - Time series data processing
    - Motion capture data management
  doc_url: https://github.com/SOMA-Bionics/movedb-core
  dev_url: https://github.com/SOMA-Bionics/movedb-core

extra:
  recipe-maintainers:
    - hudsonburke  # Your GitHub username
    # Add other maintainers if any
```

## Step 3: Submission Process

### 3.1 Get SHA256 Hash

If publishing to PyPI first:

```bash
# After uploading to PyPI, get the hash
wget https://pypi.io/packages/source/m/movedb-core/movedb_core-1.0.0.tar.gz
sha256sum movedb_core-1.0.0.tar.gz
```

Or for GitHub release:

```bash
# Download GitHub release tarball
wget https://github.com/SOMA-Bionics/movedb-core/archive/v1.0.0.tar.gz
sha256sum v1.0.0.tar.gz
```

### 3.2 Test Recipe Locally

```bash
# Install conda-build
conda install conda-build

# Test build
conda build recipes/movedb-core

# Test installation
conda create -n test-movedb movedb-core --use-local
conda activate test-movedb
python -c "import movedb; print(movedb.__version__)"
```

### 3.3 Submit Pull Request

```bash
# Add and commit your recipe
git add recipes/movedb-core/
git commit -m "Add movedb-core recipe"
git push origin main

# Create pull request on conda-forge/staged-recipes
```

## Step 4: Review Process

### 4.1 Automated Checks

The conda-forge bot will run automated checks:

- Recipe linting
- Build tests on multiple platforms
- Dependency verification

### 4.2 Community Review

Maintainers will review your PR and may request changes:

- Recipe improvements
- Dependency clarifications
- Documentation updates
- Test enhancements

### 4.3 Common Feedback Areas

- **Dependencies**: Ensure all deps are from conda-forge when possible
- **Licensing**: Clear license file and metadata
- **Testing**: Adequate test coverage in recipe
- **Maintenance**: Commit to maintaining the package

## Step 5: Post-Acceptance

### 5.1 Feedstock Creation

Once accepted, conda-forge will:

- Create a dedicated feedstock repository
- Set up automated builds
- Grant you maintainer access

### 5.2 Ongoing Maintenance

As a maintainer, you'll be responsible for:

- Updating the recipe for new versions
- Responding to build failures
- Updating dependencies
- Handling user issues

### 5.3 Version Updates

Update process for new versions:

1. Bot creates PR for version bump
2. Review and merge the PR
3. New packages are built automatically

## Alternative: Start with Personal Channel

If you want to test the waters first:

### 1. Perfect Your Current Setup

```bash
# Build and test extensively
make build
make validate

# Upload to your channel
anaconda upload dist/conda/**/*.conda
```

### 2. Gather User Feedback

- Share with potential users
- Fix any issues
- Build confidence in the package

### 3. Submit to Conda-forge Later

Once you have a stable user base and proven track record.

## Benefits of Conda-forge

### For Users

- **Trusted source**: Users trust conda-forge packages
- **Easy installation**: `conda install -c conda-forge movedb-core`
- **Better discovery**: Listed in conda-forge package index
- **Dependency management**: Better integration with other packages

### For Maintainers

- **Automated builds**: CI/CD for multiple platforms
- **Community support**: Help from conda-forge maintainers
- **Version management**: Automated update PRs
- **Quality assurance**: Standardized testing and linting

## Timeline Expectations

- **Preparation**: 1-2 weeks (ensuring package quality)
- **Submission**: 1-2 days (creating and submitting PR)
- **Review**: 1-4 weeks (community review process)
- **Acceptance**: Immediate after approval
- **First build**: Within hours of merge

## Checklist Before Submitting

- [ ] Package has stable version (1.0.0+)
- [ ] All tests pass
- [ ] Documentation is complete
- [ ] License is clear and included
- [ ] Dependencies are well-defined
- [ ] Recipe builds successfully locally
- [ ] GitHub release is created
- [ ] SHA256 hash is obtained
- [ ] Recipe follows conda-forge guidelines

## Resources

- [Conda-forge Documentation](https://conda-forge.org/docs/)
- [Staged Recipes Guidelines](https://github.com/conda-forge/staged-recipes)
- [Recipe Guidelines](https://conda-forge.org/docs/maintainer/adding_pkgs.html)
- [Example Recipes](https://github.com/conda-forge/staged-recipes/tree/main/recipes)

Would you like to proceed with conda-forge submission, or would you prefer to polish the package further first?
