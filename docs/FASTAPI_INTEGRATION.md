# MoveDB Core FastAPI Integration

This document explains how to use the FastAPI integration with SQLModel and PostgreSQL for storing and retrieving biomechanical trial data.

## Architecture Overview

The FastAPI integration provides a layered architecture that maintains separation between core analysis functionality and database persistence:

```
┌─────────────────────┐
│   Core Models       │  ← Original analysis models (Trial, Event, etc.)
│   (movedb.core)     │
└─────────────────────┘
           │
           │ Inherits/Converts
           ▼
┌─────────────────────┐
│  Enhanced Models    │  ← Database-aware models for seamless conversion
│  (api.enhanced)     │
└─────────────────────┘
           │
           │ Services layer
           ▼
┌─────────────────────┐
│  Database Models    │  ← SQLModel tables for persistence
│  (api.models)       │
└─────────────────────┘
           │
           │ FastAPI endpoints
           ▼
┌─────────────────────┐
│   REST API          │  ← HTTP interface for clients
│   (api.app)         │
└─────────────────────┘
```

## Key Features

1. **Dual Model System**: Core models for analysis, database models for persistence
2. **Enhanced Models**: Bridge between core and database with shared functionality
3. **Service Layer**: Handles conversion between different model types
4. **REST API**: Full CRUD operations for all trial data
5. **CLI Tools**: Command-line interface for database management
6. **Docker Support**: Easy deployment with PostgreSQL

## Quick Start

### 1. Database Setup

#### Option A: Using Docker Compose (Recommended)
```bash
# Start PostgreSQL and API
docker-compose up -d

# Initialize database tables
docker-compose exec api python -m movedb.api.cli init-db
```

#### Option B: Local PostgreSQL
```bash
# Set database URL
export DATABASE_URL="postgresql://user:password@localhost/movedb"

# Initialize database
python -m movedb.api.cli init-db

# Start API server
python -m movedb.api.cli serve
```

### 2. Import Data

```bash
# Import a single C3D file
python -m movedb.api.cli import-c3d path/to/trial.c3d

# Import all C3D files from directory
python -m movedb.api.cli import-directory path/to/c3d_files/

# List imported trials
python -m movedb.api.cli list-trials
```

### 3. Using the API

The API will be available at `http://localhost:8000` with automatic documentation at `http://localhost:8000/docs`.

## Programming Examples

### Basic Usage with Enhanced Models

```python
from movedb.api.enhanced_models import create_enhanced_trial_from_c3d
from movedb.api.database import engine
from sqlmodel import Session

# Load a C3D file as an enhanced trial
enhanced_trial = create_enhanced_trial_from_c3d("path/to/trial.c3d")

# Save to database
with Session(engine) as session:
    trial_id = enhanced_trial.save_to_db(session)
    print(f"Saved trial with ID: {trial_id}")

# Load from database
with Session(engine) as session:
    loaded_trial = enhanced_trial.load_from_db(session, trial_id)
    
    # Use all the normal core functionality
    gaps = loaded_trial.check_point_gaps()
    events = loaded_trial.get_events(label="Foot Strike")
    
    # Export to different formats
    loaded_trial.to_trc("output.trc")
    loaded_trial.to_mat("output.mat")
```

### Working with Core and Database Models

```python
from movedb.core.trial import Trial as CoreTrial
from movedb.api.services import TrialService
from movedb.api.database import engine
from sqlmodel import Session

# Load C3D file using core model
core_trial = CoreTrial.from_c3d_file("path/to/trial.c3d")

# Convert to database and save
with Session(engine) as session:
    service = TrialService(session)
    trial_id = service.core_to_db(core_trial)
    
    # Load back as core model
    loaded_core_trial = service.db_to_core(trial_id)
    
    # Everything works the same as before
    loaded_core_trial.run_opensim_ik("model.osim")
```

### Using the REST API

```python
import requests
import json

# Get all trials
response = requests.get("http://localhost:8000/trials/")
trials = response.json()

# Create a new trial
trial_data = {
    "name": "Test Trial",
    "session_name": "Session 1",
    "classification": "walking",
    "subject_names": ["Subject001"]
}
response = requests.post("http://localhost:8000/trials/", json=trial_data)
new_trial = response.json()

# Add events to the trial
event_data = {
    "label": "Foot Strike",
    "context": "Left",
    "frame": 100,
    "description": "Left foot strike event"
}
response = requests.post(
    f"http://localhost:8000/trials/{new_trial['id']}/events/",
    json=event_data
)
```

### Bulk Operations

```python
from movedb.api.services import BulkOperationService, AnalysisService
from movedb.api.database import engine
from sqlmodel import Session

with Session(engine) as session:
    # Import all C3D files from a directory
    bulk_service = BulkOperationService(session)
    trial_ids = bulk_service.import_trials_from_c3d_directory("/path/to/c3d_files")
    
    # Export a trial to multiple formats
    exported_files = bulk_service.export_trial_to_formats(
        trial_ids[0], 
        "/output/directory", 
        formats=["trc", "mat", "pkl"]
    )
    
    # Analysis operations
    analysis_service = AnalysisService(session)
    
    # Get statistics for a trial
    stats = analysis_service.get_trial_statistics(trial_ids[0])
    print(f"Trial has {stats['num_markers']} markers and {stats['num_events']} events")
    
    # Find trials with marker gaps
    trials_with_gaps = analysis_service.find_trials_with_gaps()
    for trial_info in trials_with_gaps:
        print(f"Trial {trial_info['trial_name']} has gaps: {trial_info['gaps']}")
```

## Database Schema

The database schema includes the following main tables:

- `trials`: Main trial metadata
- `events`: Trial events with timing information
- `force_platforms`: Force platform data and configuration
- `points_data`: Marker trajectory data (stored as JSON)
- `analogs_data`: Analog channel data (stored as JSON)

All tables include:
- `id`: UUID primary key
- `created_at`: Timestamp of creation
- `updated_at`: Timestamp of last update

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (default: postgresql://user:password@localhost/movedb)

## CLI Commands

```bash
# Database management
python -m movedb.api.cli init-db              # Initialize database tables
python -m movedb.api.cli check-db             # Check database connection

# Server management
python -m movedb.api.cli serve                # Start API server
python -m movedb.api.cli serve --reload       # Start with auto-reload

# Data import/export
python -m movedb.api.cli import-c3d file.c3d          # Import single C3D file
python -m movedb.api.cli import-directory /path/      # Import directory of C3D files
python -m movedb.api.cli export-trial <id> /output/   # Export trial to files

# Analysis
python -m movedb.api.cli list-trials          # List all trials
python -m movedb.api.cli trial-stats <id>     # Show trial statistics
python -m movedb.api.cli find-gaps            # Find trials with marker gaps
```

## API Endpoints

### Trials
- `GET /trials/` - List all trials
- `POST /trials/` - Create new trial
- `GET /trials/{id}` - Get specific trial
- `PUT /trials/{id}` - Update trial
- `DELETE /trials/{id}` - Delete trial
- `GET /trials/search/` - Search trials

### Events
- `POST /trials/{id}/events/` - Add event to trial
- `GET /trials/{id}/events/` - Get trial events
- `GET /events/{id}` - Get specific event
- `PUT /events/{id}` - Update event
- `DELETE /events/{id}` - Delete event

### Force Platforms
- `POST /trials/{id}/force-platforms/` - Add force platform
- `GET /trials/{id}/force-platforms/` - Get trial force platforms
- `GET /force-platforms/{id}` - Get specific force platform
- `PUT /force-platforms/{id}` - Update force platform
- `DELETE /force-platforms/{id}` - Delete force platform

### Data
- `POST /trials/{id}/points/` - Add points data
- `GET /trials/{id}/points/` - Get trial points data
- `PUT /points/{id}` - Update points data
- `POST /trials/{id}/analogs/` - Add analogs data
- `GET /trials/{id}/analogs/` - Get trial analogs data
- `PUT /analogs/{id}` - Update analogs data

## Migration from Core-Only Usage

If you're currently using movedb-core without the database integration, migration is straightforward:

1. Install the additional dependencies:
   ```bash
   pip install fastapi uvicorn sqlmodel psycopg2-binary
   ```

2. Your existing code continues to work unchanged:
   ```python
   from movedb.core.trial import Trial
   trial = Trial.from_c3d_file("file.c3d")
   trial.to_trc("output.trc")
   ```

3. Add database functionality when needed:
   ```python
   from movedb.api.enhanced_models import enhance_core_trial
   enhanced_trial = enhance_core_trial(trial)
   
   with Session(engine) as session:
       trial_id = enhanced_trial.save_to_db(session)
   ```

## Performance Considerations

- Large datasets (points and analogs) are stored as JSON in PostgreSQL
- Consider using PostgreSQL's JSONB type for better query performance on large datasets
- The conversion between core models and database models involves some overhead
- For high-frequency operations, consider keeping data in core models and periodically syncing to database

## Future Enhancements

- Real-time data streaming endpoints
- Advanced query capabilities using PostgreSQL's JSON operators
- Caching layer for frequently accessed trials
- Integration with cloud storage for large datasets
- GraphQL endpoint for complex queries
