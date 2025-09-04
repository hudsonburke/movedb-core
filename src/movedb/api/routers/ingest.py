from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Any, Optional, List
import os
from pathlib import Path
from ..dependencies import SessionDep
from ..services.vicon_db_ingest import scan_vicon_directory
from ...ingest.c3d_adapter import C3DAdapter

router = APIRouter(prefix="/ingest", tags=["ingest"])

@router.post("/scan")
def scan_vicon_database(
    root: str = Query(..., description="Root directory of the Vicon Nexus database"),
    *,
    session: SessionDep
) -> dict[str, Any]:
    """Scan a Vicon Nexus database directory structure."""
    try:
        return scan_vicon_directory(session=session, root=root)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/directory")
def ingest_directory(
    background_tasks: BackgroundTasks,
    directory_path: str = Query(..., description="Directory containing C3D files"),
    recursive: bool = Query(True, description="Search subdirectories recursively"),
    file_pattern: str = Query("*.c3d", description="File pattern to match"),
    batch_size: int = Query(10, description="Number of files to process in each batch"),
    *,
    session: SessionDep
):
    """Ingest all C3D files from a directory."""
    
    if not os.path.exists(directory_path):
        raise HTTPException(status_code=400, detail="Directory not found")
    
    if not os.path.isdir(directory_path):
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    # Find all matching files
    path = Path(directory_path)
    if recursive:
        files = list(path.rglob(file_pattern))
    else:
        files = list(path.glob(file_pattern))
    
    c3d_files = [f for f in files if f.suffix.lower() == '.c3d']
    
    if not c3d_files:
        return {
            "message": "No C3D files found",
            "directory": directory_path,
            "files_found": 0
        }
    
    # Process files in background
    background_tasks.add_task(
        process_files_batch,
        session,
        c3d_files,
        batch_size
    )
    
    return {
        "message": f"Started ingesting {len(c3d_files)} C3D files",
        "directory": directory_path,
        "files_found": len(c3d_files),
        "status": "processing_in_background"
    }

@router.post("/file")
def ingest_single_file(
    file_path: str = Query(..., description="Path to C3D file"),
    trial_name: Optional[str] = Query(None, description="Override trial name"),
    *,
    session: SessionDep
):
    """Ingest a single C3D file."""
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="File not found")
    
    if not file_path.lower().endswith('.c3d'):
        raise HTTPException(status_code=400, detail="File must be a C3D file")
    
    try:
        # Process C3D file
        adapter = C3DAdapter.from_file(file_path)
        
        # Create trial from C3D data
        name = trial_name or Path(file_path).stem
        trial = adapter.to_trial(name=name)
        
        # Save to database
        session.add(trial)
        session.commit()
        session.refresh(trial)
        
        return {
            "message": "File ingested successfully",
            "file_path": file_path,
            "trial_id": trial.id,
            "trial_name": trial.name,
            "markers_count": len(trial.markers),
            "analogs_count": len(trial.analogs),
            "forceplates_count": len(trial.forceplates),
            "events_count": len(trial.events)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.get("/status")
def get_ingest_status():
    """Get the current status of ingest operations."""
    # This would typically check a task queue or background job status
    # For now, return a simple status
    return {
        "status": "ready",
        "message": "Ingest service is operational"
    }

@router.get("/validate/{trial_id}")
def validate_ingested_trial(trial_id: int, session: SessionDep):
    """Validate that an ingested trial has correct data structure."""
    from ...models import Trial
    
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    validation_results = {
        "trial_id": trial_id,
        "trial_name": trial.name,
        "valid": True,
        "warnings": [],
        "errors": []
    }
    
    # Check basic trial properties
    if not trial.name:
        validation_results["errors"].append("Trial name is missing")
        validation_results["valid"] = False
    
    # Check if trial has any data
    if not trial.markers and not trial.analogs and not trial.forceplates:
        validation_results["warnings"].append("Trial has no motion capture data")
    
    # Check markers
    marker_names = [m.name for m in trial.markers]
    if len(marker_names) != len(set(marker_names)):
        validation_results["warnings"].append("Duplicate marker names found")
    
    for marker in trial.markers:
        if not marker.data:
            validation_results["warnings"].append(f"Marker '{marker.name}' has no data")
    
    # Check analogs
    analog_names = [a.name for a in trial.analogs]
    if len(analog_names) != len(set(analog_names)):
        validation_results["warnings"].append("Duplicate analog channel names found")
    
    for analog in trial.analogs:
        if not analog.data:
            validation_results["warnings"].append(f"Analog '{analog.name}' has no data")
    
    # Check force plates
    for forceplate in trial.forceplates:
        if not forceplate.data:
            validation_results["warnings"].append(f"Force plate '{forceplate.name}' has no data")
    
    return validation_results

def process_files_batch(session: SessionDep, files: List[Path], batch_size: int):
    """Background task to process files in batches."""
    # This would typically be implemented with a proper task queue like Celery
    # For now, it's a simple synchronous function
    
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        
        for file_path in batch:
            try:
                adapter = C3DAdapter.from_file(str(file_path))
                trial = adapter.to_trial(name=file_path.stem)
                
                session.add(trial)
                session.commit()
                session.refresh(trial)
                
            except Exception as e:
                # Log error (in a real implementation, you'd use proper logging)
                print(f"Error processing {file_path}: {str(e)}")
                continue


