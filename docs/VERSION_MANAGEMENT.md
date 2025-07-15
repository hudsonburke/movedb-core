# Version Management Guide

## Overview

The `movedb-core` project includes automated version bumping tools to ensure consistent version numbers across all files and simplify the release process.

## Version Bumping Script

The `bump_version.py` script automatically updates version numbers in:

- `src/movedb/__init__.py` - Main package version
- `pyproject.toml` - Package metadata
- `conda-recipe/meta.yaml` - Conda package recipe

## Usage Options

### 1. Direct Script Usage

```bash
# Show help
python bump_version.py

# Bump patch version (0.1.0 -> 0.1.1)
python bump_version.py patch

# Bump minor version (0.1.0 -> 0.2.0)
python bump_version.py minor

# Bump major version (0.1.0 -> 1.0.0)
python bump_version.py major

# Set specific version
python bump_version.py 0.2.5

# Bump and create git tag
python bump_version.py patch --tag

# Bump, tag, and push to remote
python bump_version.py minor --tag --push
```

### 2. Makefile Commands (Recommended)

```bash
# Version bumping
make bump-patch      # Bump patch version
make bump-minor      # Bump minor version
make bump-major      # Bump major version

# Set specific version
make bump-version VERSION=1.2.3

# Full release workflow (bump + tag + push)
make release-patch   # Patch release
make release-minor   # Minor release
make release-major   # Major release
```

## Typical Release Workflow

### For Patch Releases (Bug fixes)

```bash
# 1. Bump version and create tag
make release-patch

# 2. Build new package
make build

# 3. Upload to conda (optional)
conda upload dist/conda/noarch/movedb-core-*-*.conda
```

### For Minor Releases (New features)

```bash
# 1. Bump version and create tag
make release-minor

# 2. Build new package
make build

# 3. Upload to conda (optional)
conda upload dist/conda/noarch/movedb-core-*-*.conda
```

### For Major Releases (Breaking changes)

```bash
# 1. Bump version and create tag
make release-major

# 2. Build new package
make build

# 3. Upload to conda (optional)
conda upload dist/conda/noarch/movedb-core-*-*.conda
```

## Manual Workflow (Step by Step)

If you prefer more control over the process:

```bash
# 1. Bump version (without auto-tagging)
make bump-patch

# 2. Review changes
git diff

# 3. Commit changes
git add -A
git commit -m "Bump version to $(python -c 'import src.movedb; print(src.movedb.__version__)')"

# 4. Create and push tag
VERSION=$(python -c 'import sys; sys.path.insert(0, "src"); import movedb; print(movedb.__version__)')
git tag v$VERSION
git push origin main
git push origin v$VERSION

# 5. Build package
make build

# 6. Upload to conda
conda upload dist/conda/noarch/movedb-core-$VERSION-*.conda
```

## Version Management Best Practices

### Semantic Versioning

- **Patch** (x.y.Z): Bug fixes, no API changes
- **Minor** (x.Y.0): New features, backward compatible
- **Major** (X.0.0): Breaking changes, API changes

### Pre-Release Checklist

- [ ] All tests pass: `make test`
- [ ] Code is formatted: `make format`
- [ ] Linting passes: `make lint`
- [ ] Documentation is updated
- [ ] CHANGELOG is updated (if maintained)

### Release Checklist

- [ ] Version bumped: `make bump-*` or `make release-*`
- [ ] Git tag created and pushed
- [ ] Package builds successfully: `make build`
- [ ] Package uploaded to conda: `conda upload ...`
- [ ] GitHub release created (optional)

## Troubleshooting

### Version Mismatch

If you see version mismatches, run the version bump script again:

```bash
python bump_version.py $(python -c 'import sys; sys.path.insert(0, "src"); import movedb; print(movedb.__version__)')
```

### Package Already Exists

If conda upload fails with "package already exists":

1. Check your version: `python -c 'import sys; sys.path.insert(0, "src"); import movedb; print(movedb.__version__)'`
2. Bump to a new version: `make bump-patch`
3. Rebuild: `make build`
4. Upload again: `conda upload ...`

### Git Tag Conflicts

If git tag creation fails:

```bash
# List existing tags
git tag -l

# Delete local tag if needed
git tag -d v1.2.3

# Delete remote tag if needed
git push origin :refs/tags/v1.2.3
```

## Integration with CI/CD

The version management integrates with GitHub Actions:

- Tags trigger release workflows
- Consistent versions across all files
- Automated package building on tags

## Files Updated by Version Bumping

The script automatically updates:

1. **`src/movedb/__init__.py`** - `__version__ = "x.y.z"`
2. **`pyproject.toml`** - `version = "x.y.z"`
3. **`conda-recipe/meta.yaml`** - `{% set version = "x.y.z" %}`

This ensures all package metadata stays in sync across build systems.

## Dependency Management

When updating dependencies, ensure consistency across all configuration files:

### Core Dependencies

Update in these locations:
- **`pyproject.toml`** - Main package dependencies
- **`environment.yml`** - Development environment
- **`environment-opensim.yml`** - OpenSim-specific environment  
- **`conda-recipe/meta.yaml`** - Conda package dependencies

### Documentation Dependencies

When adding/removing dependencies, also update:
- **`README.md`** - Requirements section
- **`docs/INSTALL.md`** - Installation instructions
- **`docs/DEVELOPMENT.md`** - Development setup
- **`CHANGELOG.md`** - Document the changes

### Version Pinning Strategy

- **Minimum versions**: Use `>=` for compatibility
- **Major version limits**: Use `<next_major` for breaking changes
- **Conda vs PyPI**: Some packages (like `opensim`) are conda-only
