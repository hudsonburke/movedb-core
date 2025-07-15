# Documentation Index

This directory contains comprehensive documentation for movedb-core.

## Quick Navigation

### 📦 Installation & Setup

- **[INSTALL.md](INSTALL.md)** - Complete installation guide
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Developer setup and workflow

### 🔧 Development

- **[ROADMAP_V1.md](ROADMAP_V1.md)** - Version 1.0.0 roadmap and timeline
- **[LINTING.md](LINTING.md)** - Code quality and linting guide
- **[VERSION_MANAGEMENT.md](VERSION_MANAGEMENT.md)** - Version bumping and release process
- **[../CHANGELOG.md](../CHANGELOG.md)** - Project changelog and version history

### 🚚 Packaging & Distribution

- **[CONDA_PACKAGING.md](CONDA_PACKAGING.md)** - Complete conda packaging and distribution guide
- **[CONDA_FORGE_SUBMISSION.md](CONDA_FORGE_SUBMISSION.md)** - How to submit to conda-forge

### 🏗️ Design & Architecture

- **[API_DESIGN.md](API_DESIGN.md)** - API design principles and structure

### 🔄 CI/CD & Automation

- **[GITHUB_ACTIONS.md](GITHUB_ACTIONS.md)** - Complete GitHub Actions CI/CD guide

### 🧪 Testing

- **[PYTEST_SETUP.md](PYTEST_SETUP.md)** - Complete testing guide and setup

## Getting Started

New to the project? Start here:

1. **Installation**: [INSTALL.md](INSTALL.md)
2. **Development Setup**: [DEVELOPMENT.md](DEVELOPMENT.md)
3. **Contributing**: Check the main [project README](../README.md)

## For Maintainers

Working on releases and distribution:

1. **Version Management**: [VERSION_MANAGEMENT.md](VERSION_MANAGEMENT.md)
2. **Conda Packaging**: [CONDA_PACKAGING.md](CONDA_PACKAGING.md)
3. **v1.0.0 Roadmap**: [ROADMAP_V1.md](ROADMAP_V1.md)
4. **Conda-forge Submission**: [CONDA_FORGE_SUBMISSION.md](CONDA_FORGE_SUBMISSION.md)

## Documentation Standards

All documentation follows automated standards enforced by CI:

- **Style Consistency**: Enforced by markdownlint with project-specific rules
- **Clear Structure**: Use descriptive titles and consistent formatting
- **Code Examples**: Include helpful examples where appropriate  
- **Link Validation**: Internal links checked automatically
- **Line Length**: Maximum 120 characters (configurable)
- **Cross-References**: Link between related documents using relative paths

### Automated Enforcement

Documentation quality is maintained through:

- **CI Pipeline**: markdownlint runs on every PR and push
- **Local Development**: `make lint-docs` checks documentation locally
- **Auto-fixing**: `make lint-docs-fix` automatically fixes common issues
- **Pre-commit Hooks**: Optional pre-commit setup for instant feedback

### Local Setup

```bash
# Install markdownlint (one-time setup)
npm install -g markdownlint-cli

# Check documentation
make lint-docs

# Auto-fix documentation issues
make lint-docs-fix

# Run all linting (code + docs)
make lint
```

## Contributing to Documentation

Documentation improvements are always welcome! Please:

1. Keep the style consistent with existing docs
2. Update this index when adding new files
3. Test any installation or setup instructions
4. Use relative links within the docs/ directory
