# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `numpydantic>=1.0.0` for enhanced array validation and type safety
- `pandera-polars>=0.20.0` for robust data validation with Polars DataFrames
- Comprehensive data validation throughout the codebase

### Changed
- Enhanced data validation using numpydantic for NumPy arrays
- Improved DataFrame validation with pandera-polars
- Updated all environment files and documentation to include new dependencies

### Removed
- `loguru` dependency (replaced with standard warnings module for better compatibility)

### Fixed
- Fixed undefined `logger` reference in `opensim_exporters.py` by replacing with `warnings.warn()`

## [0.3.0] - 2024

### Added
- Core functionality for movement database operations
- C3D file I/O support
- OpenSim integration
- Time series processing
- Force platform support
- Basic data validation
- Type safety with Pydantic models

### Infrastructure
- Complete CI/CD pipeline
- Conda packaging
- Documentation structure
- Testing framework
