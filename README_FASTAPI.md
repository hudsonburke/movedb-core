# FastAPI Integration for MoveDB Core

This implementation provides a comprehensive FastAPI application with SQLModel and PostgreSQL for storing and managing biomechanical trial data while maintaining full compatibility with the existing core analysis functionality.

## 🏗️ Architecture

The integration follows a layered architecture that preserves the original core functionality while adding database persistence:

```
Core Models (Analysis) ↔ Enhanced Models (Bridge) ↔ Database Models (Persistence) ↔ REST API
```

### Key Components

1. **Core Models** (`movedb.core.*`) - Original analysis-focused models
2. **Database Models** (`movedb.api.models`) - SQLModel tables for PostgreSQL
3. **Enhanced Models** (`movedb.api.enhanced_models`) - Bridge classes with both capabilities
4. **Service Layer** (`movedb.api.services`) - Conversion and business logic
5. **REST API** (`movedb.api.app`) - HTTP endpoints
6. **CLI Tools** (`movedb.api.cli`) - Command-line management

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install fastapi uvicorn sqlmodel psycopg2-binary python-multipart
```

### 2. Start PostgreSQL

#### Using Docker (Recommended)
```bash
docker-compose up -d postgres
```

#### Using local PostgreSQL
```bash
export DATABASE_URL="postgresql://user:password@localhost/movedb"
```

### 3. Initialize Database

```bash
python -m movedb.api.cli init-db
```

### 4. Start API Server

```bash
python -m movedb.api.cli serve
```

The API will be available at `http://localhost:8000` with docs at `http://localhost:8000/docs`.

## 📊 Usage Examples

### Basic Workflow

```python
from movedb.api.enhanced_models import create_enhanced_trial_from_c3d
from movedb.api.database import engine
from sqlmodel import Session

# Load C3D file as enhanced trial (works like core model)
trial = create_enhanced_trial_from_c3d("path/to/trial.c3d")

# Use all normal analysis functionality
gaps = trial.check_point_gaps()
events = trial.get_events(label="Foot Strike")
trial.to_trc("output.trc")

# Save to database when needed
with Session(engine) as session:
    trial_id = trial.save_to_db(session)
```

### Converting Existing Code

Your existing code continues to work unchanged:

```python
# This still works exactly the same
from movedb.core.trial import Trial
trial = Trial.from_c3d_file("file.c3d")
trial.run_opensim_ik("model.osim")

# Add database functionality when needed
from movedb.api.enhanced_models import enhance_core_trial
enhanced = enhance_core_trial(trial)
with Session(engine) as session:
    trial_id = enhanced.save_to_db(session)
```

### Service Layer Usage

```python
from movedb.api.services import TrialService, AnalysisService
from sqlmodel import Session

with Session(engine) as session:
    # Import C3D and save to database
    core_trial = CoreTrial.from_c3d_file("file.c3d")
    service = TrialService(session)
    trial_id = service.core_to_db(core_trial)
    
    # Load back as core model for analysis
    loaded_trial = service.db_to_core(trial_id)
    
    # Analysis operations
    analysis = AnalysisService(session)
    stats = analysis.get_trial_statistics(trial_id)
    gaps = analysis.find_trials_with_gaps()
```

### REST API Usage

```python
import requests

# Get all trials
trials = requests.get("http://localhost:8000/trials/").json()

# Create new trial
trial_data = {
    "name": "New Trial",
    "session_name": "Session 1",
    "classification": "walking"
}
new_trial = requests.post("http://localhost:8000/trials/", json=trial_data).json()

# Add events
event_data = {
    "label": "Foot Strike",
    "context": "Left", 
    "frame": 100
}
requests.post(f"http://localhost:8000/trials/{new_trial['id']}/events/", json=event_data)
```

## 🛠️ CLI Commands

```bash
# Database management
python -m movedb.api.cli init-db              # Initialize database
python -m movedb.api.cli check-db             # Test connection

# Server
python -m movedb.api.cli serve                # Start API server
python -m movedb.api.cli serve --reload       # Development mode

# Data operations
python -m movedb.api.cli import-c3d file.c3d          # Import C3D file
python -m movedb.api.cli import-directory /path/      # Import directory
python -m movedb.api.cli export-trial <id> /output/   # Export trial

# Analysis
python -m movedb.api.cli list-trials          # List all trials
python -m movedb.api.cli trial-stats <id>     # Show trial statistics
python -m movedb.api.cli find-gaps            # Find trials with gaps
```

## 📡 API Endpoints

### Core Endpoints

- `GET /health` - Health check
- `GET /trials/` - List trials (with pagination)
- `POST /trials/` - Create trial
- `GET /trials/{id}` - Get trial details
- `PUT /trials/{id}` - Update trial
- `DELETE /trials/{id}` - Delete trial
- `GET /trials/search/` - Search trials

### Events
- `POST /trials/{id}/events/` - Add event
- `GET /trials/{id}/events/` - Get trial events
- `GET /events/{id}` - Get event details
- `PUT /events/{id}` - Update event
- `DELETE /events/{id}` - Delete event

### Force Platforms
- `POST /trials/{id}/force-platforms/` - Add force platform
- `GET /trials/{id}/force-platforms/` - Get trial force platforms
- `GET /force-platforms/{id}` - Get force platform details
- `PUT /force-platforms/{id}` - Update force platform
- `DELETE /force-platforms/{id}` - Delete force platform

### Data
- `POST /trials/{id}/points/` - Add points data
- `GET /trials/{id}/points/` - Get trial points data
- `PUT /points/{id}` - Update points data
- `POST /trials/{id}/analogs/` - Add analogs data
- `GET /trials/{id}/analogs/` - Get trial analogs data
- `PUT /analogs/{id}` - Update analogs data

## 🐳 Docker Deployment

The included `docker-compose.yml` sets up both PostgreSQL and the API:

```bash
docker-compose up -d          # Start all services
docker-compose logs api       # View API logs
docker-compose down           # Stop all services
```

## 🔧 Configuration

### Environment Variables

- `DATABASE_URL` - PostgreSQL connection string
  - Default: `postgresql://movedb_user:movedb_password@localhost:5432/movedb`

### Database Schema

The schema includes these main tables:
- `trials` - Trial metadata
- `events` - Trial events
- `force_platforms` - Force platform data
- `points_data` - Marker trajectories (JSON)
- `analogs_data` - Analog channels (JSON)

All tables have UUID primary keys and timestamp fields.

## 🎯 Key Features

1. **Backward Compatibility** - Existing core model code works unchanged
2. **Enhanced Models** - Bridge classes with both analysis and database capabilities
3. **Flexible Storage** - Complex data stored as JSON in PostgreSQL
4. **REST API** - Full CRUD operations with automatic documentation
5. **CLI Tools** - Command-line interface for all operations
6. **Docker Support** - Easy deployment with PostgreSQL
7. **Service Layer** - Clean separation between models and database operations

## 🔄 Migration Guide

### From Core-Only Usage

1. Install additional dependencies:
   ```bash
   pip install fastapi uvicorn sqlmodel psycopg2-binary
   ```

2. Existing code continues to work:
   ```python
   # No changes needed
   from movedb.core.trial import Trial
   trial = Trial.from_c3d_file("file.c3d")
   ```

3. Add database functionality incrementally:
   ```python
   # When you want database storage
   from movedb.api.enhanced_models import enhance_core_trial
   enhanced = enhance_core_trial(trial)
   
   with Session(engine) as session:
       trial_id = enhanced.save_to_db(session)
   ```

### Database Schema Updates

The database schema is designed to be extensible. New fields can be added to the JSON columns without breaking existing data.

## 🚧 Performance Considerations

- Large datasets (trajectories, analog data) stored as JSON
- Consider JSONB for better query performance on large datasets
- Core ↔ Database conversion has some overhead
- Keep frequently used data in core models, sync to database periodically

## 🔮 Future Enhancements

- Real-time streaming endpoints
- Advanced JSON queries using PostgreSQL operators
- Caching layer for frequently accessed data
- Cloud storage integration for large datasets
- GraphQL endpoint for complex queries
- WebSocket support for real-time updates

## 📝 Example Script

Run the comprehensive example:

```bash
python examples/fastapi_integration_example.py
```

This demonstrates:
- Database setup
- Core to enhanced model conversion
- Service layer operations
- REST API usage
- Export functionality

## 🤝 Contributing

The FastAPI integration maintains the same contribution guidelines as the core library. When adding new features:

1. Ensure backward compatibility with core models
2. Add corresponding database models and API endpoints
3. Include tests for both core and database functionality
4. Update documentation and examples

## 📄 License

Same MIT license as the core MoveDB library.
