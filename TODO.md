# MoveDB Core

## Core Features

- [ ] Add plotting for core models

### OpenSim integration

- [ ] Add support for OpenSim files in database
- [ ] Implement OpenSim pipelines

### API

- [ ] OpenSim

### Database

- [ ] Local SQLite support
- [ ] Supabase integration

### CLI

- [ ] Would this be useful?

### Documentation

- [ ] Update README
- [ ] Create installation guide using uv
- [ ] Write usage examples

### Testing

- [ ] Write unit tests for core functionalities
- [ ] Write integration tests for database interactions
- [ ] Set up continuous integration (CI) for automated testing

## Code Cleanup

- [ ] Add docstrings to all public modules, classes, and functions.
- [ ] Simplify the `get_event_sequences` method in the `Trial` model.

## Feature Implementation

- [ ] Finish the implementation of the `export_force_platforms` function in `osim/write.py`.
- [ ] Implement data visualization features, potentially using `pyvista`.
- [ ] Implement asynchronous processing for database operations to improve performance.

## Hail Mary

- Rust rust rewrite of core library if performance becomes a bottleneck
  - And so we can be cool
