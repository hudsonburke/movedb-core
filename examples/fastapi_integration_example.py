#!/usr/bin/env python3
"""
Example script demonstrating MoveDB Core FastAPI integration.

This script shows how to:
1. Set up the database
2. Import C3D files
3. Use enhanced models for analysis
4. Export data in different formats
5. Query the database via REST API

Prerequisites:
- PostgreSQL running (use docker-compose up -d)
- C3D files in the test data directory
"""

import os
import sys
from pathlib import Path
import requests
import json

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from movedb.api.database import engine, create_db_and_tables
from movedb.api.enhanced_models import create_enhanced_trial_from_c3d, enhance_core_trial
from movedb.api.services import TrialService, BulkOperationService, AnalysisService
from movedb.core.trial import Trial as CoreTrial
from sqlmodel import Session


def setup_database():
    """Initialize the database tables."""
    print("🔧 Setting up database...")
    try:
        create_db_and_tables()
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False


def example_core_to_enhanced_workflow():
    """Demonstrate converting core models to enhanced models."""
    print("\n📊 Example 1: Core to Enhanced Model Workflow")
    
    # Find a test C3D file
    test_data_dir = Path("tests/data")
    c3d_files = list(test_data_dir.glob("**/*.c3d")) if test_data_dir.exists() else []
    
    if not c3d_files:
        print("⚠️  No C3D files found in tests/data directory")
        print("   Creating a mock trial instead...")
        
        # Create a mock trial for demonstration
        from movedb.core.events import Event
        from movedb.core.time_series import Points, MarkerTrajectory
        from movedb.core.force_platforms import EZForcePlatform
        import polars as pl
        import numpy as np
        
        # Create mock marker data
        n_frames = 1000
        trajectories = {}
        for marker in ["LASI", "RASI", "LPSI", "RPSI"]:
            data = pl.DataFrame({
                "x": np.random.normal(0, 10, n_frames).tolist(),
                "y": np.random.normal(0, 10, n_frames).tolist(), 
                "z": np.random.normal(100, 5, n_frames).tolist(),
                "residual": np.random.normal(0, 1, n_frames).tolist(),
            })
            trajectories[marker] = MarkerTrajectory(data=data, description=f"{marker} marker")
        
        points = Points(
            first_frame=1,
            last_frame=n_frames,
            rate=100.0,
            units="mm",
            trajectories=trajectories
        )
        
        # Create mock events
        events = [
            Event(label="Foot Strike", context="Left", frame=100),
            Event(label="Foot Off", context="Left", frame=600),
            Event(label="Foot Strike", context="Right", frame=350),
            Event(label="Foot Off", context="Right", frame=850),
        ]
        
        # Create mock analogs (empty for this example)
        from movedb.core.time_series import Analogs
        analogs = Analogs(
            first_frame=1,
            last_frame=n_frames * 10,  # Usually higher rate
            rate=1000.0,
            channels={}
        )
        
        core_trial = CoreTrial(
            name="Mock Trial",
            session_name="Example Session",
            subject_names=["Subject001"],
            classification="walking",
            parameters={"speed": "self-selected"},
            events=events,
            points=points,
            analogs=analogs,
            force_platforms=[]
        )
    else:
        # Load real C3D file
        c3d_file = c3d_files[0]
        print(f"📁 Loading C3D file: {c3d_file}")
        core_trial = CoreTrial.from_c3d_file(str(c3d_file))
    
    print(f"✅ Loaded trial: {core_trial.name}")
    print(f"   - Duration: {getattr(core_trial.points, 'total_frames', 0)} frames")
    print(f"   - Events: {len(core_trial.events)}")
    print(f"   - Markers: {len(getattr(core_trial.points, 'trajectories', {}))}")
    
    # Convert to enhanced model
    enhanced_trial = enhance_core_trial(core_trial)
    print("✅ Converted to enhanced model")
    
    # Save to database
    with Session(engine) as session:
        trial_id = enhanced_trial.save_to_db(session)
        print(f"✅ Saved to database with ID: {trial_id}")
        
        # Load back from database
        loaded_trial = enhanced_trial.load_from_db(session, trial_id)
        print(f"✅ Loaded from database: {loaded_trial.name}")
        
        # Demonstrate that all core functionality still works
        if hasattr(loaded_trial, 'points') and loaded_trial.points:
            gaps = loaded_trial.check_point_gaps()
            print(f"✅ Checked point gaps: {len(gaps)} markers analyzed")
        
        # Export to different formats
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        if hasattr(loaded_trial, 'points') and loaded_trial.points:
            trc_path = output_dir / f"{loaded_trial.name}.trc"
            loaded_trial.to_trc(str(trc_path))
            print(f"✅ Exported TRC: {trc_path}")
        
        mat_path = output_dir / f"{loaded_trial.name}.mat"
        loaded_trial.to_mat(str(mat_path))
        print(f"✅ Exported MAT: {mat_path}")
        
        return trial_id


def example_service_layer():
    """Demonstrate using the service layer."""
    print("\n🔧 Example 2: Service Layer Operations")
    
    with Session(engine) as session:
        # Bulk operations
        bulk_service = BulkOperationService(session)
        
        # Analysis operations
        analysis_service = AnalysisService(session)
        
        # Get all trials and show statistics
        from sqlmodel import select
        from movedb.api.models import Trial as DBTrial
        
        statement = select(DBTrial)
        trials = session.exec(statement).all()
        
        print(f"📊 Found {len(trials)} trials in database")
        
        for trial in trials[:3]:  # Show first 3 trials
            try:
                stats = analysis_service.get_trial_statistics(trial.id)
                print(f"   - {stats['name']}: {stats['duration_seconds']:.1f}s, {stats['num_events']} events")
            except Exception as e:
                print(f"   - {trial.name}: Error getting stats - {e}")
        
        # Find trials with gaps
        trials_with_gaps = analysis_service.find_trials_with_gaps()
        print(f"🔍 Found {len(trials_with_gaps)} trials with marker gaps")


def example_rest_api():
    """Demonstrate using the REST API."""
    print("\n🌐 Example 3: REST API Usage")
    
    api_url = "http://localhost:8000"
    
    try:
        # Test if API is running
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code != 200:
            print("⚠️  API server not responding. Start it with:")
            print("   python -m movedb.api.cli serve")
            return
        
        print("✅ API server is running")
        
        # Get all trials
        response = requests.get(f"{api_url}/trials/")
        trials = response.json()
        print(f"📊 API returned {len(trials)} trials")
        
        if trials:
            # Get details of first trial
            trial = trials[0]
            trial_id = trial['id']
            
            response = requests.get(f"{api_url}/trials/{trial_id}")
            trial_details = response.json()
            print(f"📋 Trial details: {trial_details['name']}")
            print(f"   - Events: {len(trial_details['events'])}")
            print(f"   - Force platforms: {len(trial_details['force_platforms'])}")
            
            # Get events for this trial
            response = requests.get(f"{api_url}/trials/{trial_id}/events/")
            events = response.json()
            print(f"🎯 Found {len(events)} events")
            
            for event in events[:3]:  # Show first 3 events
                print(f"   - {event['label']} ({event['context']}): frame {event['frame']}")
        
        # Create a new trial via API
        new_trial_data = {
            "name": "API Test Trial",
            "session_name": "API Demo Session",
            "classification": "testing",
            "subject_names": ["TestSubject001"],
            "parameters": {"created_via": "api_example"}
        }
        
        response = requests.post(f"{api_url}/trials/", json=new_trial_data)
        if response.status_code == 200:
            new_trial = response.json()
            print(f"✅ Created new trial via API: {new_trial['id']}")
            
            # Add an event to the new trial
            event_data = {
                "label": "Test Event",
                "context": "API",
                "frame": 42,
                "description": "Created via API example"
            }
            
            response = requests.post(
                f"{api_url}/trials/{new_trial['id']}/events/",
                json=event_data
            )
            
            if response.status_code == 200:
                new_event = response.json()
                print(f"✅ Added event to trial: {new_event['label']}")
        
    except requests.exceptions.ConnectionError:
        print("⚠️  Could not connect to API server. Start it with:")
        print("   python -m movedb.api.cli serve")
    except Exception as e:
        print(f"❌ Error with API: {e}")


def main():
    """Run all examples."""
    print("🚀 MoveDB Core FastAPI Integration Examples")
    print("=" * 50)
    
    # Check database connection
    try:
        with Session(engine) as session:
            session.exec("SELECT 1").first()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("   Make sure PostgreSQL is running (docker-compose up -d)")
        return
    
    # Setup database
    if not setup_database():
        return
    
    # Run examples
    try:
        trial_id = example_core_to_enhanced_workflow()
        example_service_layer()
        example_rest_api()
        
        print("\n🎉 All examples completed successfully!")
        print("\nNext steps:")
        print("1. Explore the API documentation at http://localhost:8000/docs")
        print("2. Try importing your own C3D files:")
        print("   python -m movedb.api.cli import-c3d your_file.c3d")
        print("3. Start the API server:")
        print("   python -m movedb.api.cli serve")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
