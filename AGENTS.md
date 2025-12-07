# Agent Guidelines for MoveDB Core

## Code Style

### Imports

- Order: stdlib → third-party → local (sorted within groups)
- Use modern Python 3.12+ syntax: `list[str]`, `dict[str, Any]`, `int | None`
- Avoid `from typing import List, Dict, Optional, Union`

### Type Hints

- All functions must have type hints for parameters and return values
- Use `| None` instead of `Optional[T]`
- Use `list[T]` instead of `List[T]`
- Use `dict[K, V]` instead of `Dict[K, V]`

### Naming

- Classes: `PascalCase` (e.g., `Trial`, `HDF5TrialStorage`)
- Functions/methods: `snake_case` (e.g., `load_markers`, `export_to_trc`)
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

### Documentation

- All public functions/classes need docstrings
- Format: Google-style with Args/Returns/Example sections
- Include usage examples in complex methods

### Error Handling

- Use descriptive `ValueError` for validation errors
- Use `FileNotFoundError` for missing files
- Include helpful context in error messages (what failed, why, how to fix)
- Prefer early returns for error conditions

### Logging

- Use `loguru` for all logging: `from loguru import logger`
- Levels: `logger.debug()` for details, `logger.info()` for progress, `logger.success()` for completion
- Include context in log messages (file paths, counts, etc.)

### Pydantic Models

- Use `Field()` with descriptions for all fields
- Set `model_config = ConfigDict(arbitrary_types_allowed=True)` when needed
- Provide `to_dict()` methods for serialization

### Data Validation

- Validate shapes before writing to HDF5
- Validate rates/frequencies are positive
- Check array dimensions match expected values
- Provide clear error messages with actual vs expected values
