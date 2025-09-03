from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks
from typing import Optional
import os
import tempfile
import shutil
import datetime
from ..dependencies import SessionDep
from ...convert.c3d_adapter import C3DAdapter
from ...models import File as FileModel

router = APIRouter(
    prefix="/upload",
    tags=["upload"]
)

@router.post("/c3d")
async def upload_c3d_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    trial_name: Optional[str] = None,
    *,
    session: SessionDep
):
    """Upload and process a C3D file."""
    
    # Validate file extension
    filename = file.filename or "unknown.c3d"
    if not filename.lower().endswith('.c3d'):
        raise HTTPException(status_code=400, detail="File must be a C3D file")
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.c3d') as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_path = temp_file.name
    
    try:
        # Process C3D file
        adapter = C3DAdapter.from_file(temp_path)
        
        # Create trial from C3D data
        trial = adapter.to_trial(
            name=trial_name or filename.replace('.c3d', '')
        )
        
        # Save to database
        session.add(trial)
        session.commit()
        session.refresh(trial)
        
        # Clean up temporary file in background
        background_tasks.add_task(os.unlink, temp_path)
        
        return {
            "message": "C3D file uploaded and processed successfully",
            "trial_id": trial.id,
            "trial_name": trial.name,
            "markers_count": len(trial.markers),
            "analogs_count": len(trial.analogs),
            "forceplates_count": len(trial.forceplates),
            "events_count": len(trial.events)
        }
        
    except Exception as e:
        # Clean up temporary file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=f"Error processing C3D file: {str(e)}")

@router.post("/file")
async def upload_generic_file(
    file: UploadFile = File(...),
    file_path: str = "/tmp/",  # Default path, should be configurable
    *,
    session: SessionDep
):
    """Upload a generic file and store metadata."""
    
    filename = file.filename or "unknown"
    
    # Create full file path
    full_path = os.path.join(file_path, filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    # Save file to disk
    with open(full_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Get file stats
    file_stats = os.stat(full_path)
    
    # Store file metadata in database
    file_record = FileModel(
        file_name=filename,
        file_path=full_path,
        file_type=file.content_type or "application/octet-stream",
        file_size=file_stats.st_size,
        file_hash="",  # Will be computed by model validator
        date_created=datetime.datetime.fromtimestamp(file_stats.st_ctime),
        last_modified=datetime.datetime.fromtimestamp(file_stats.st_mtime)
    )
    
    session.add(file_record)
    session.commit()
    session.refresh(file_record)
    
    return {
        "message": "File uploaded successfully",
        "file_id": file_record.id,
        "filename": file_record.file_name,
        "size": file_record.file_size,
        "file_type": file_record.file_type,
        "path": file_record.file_path
    }

@router.get("/formats")
async def get_supported_formats():
    """Get list of supported file formats for upload."""
    return {
        "supported_formats": {
            "c3d": {
                "description": "C3D motion capture files",
                "extensions": [".c3d"],
                "endpoint": "/upload/c3d"
            },
            "generic": {
                "description": "Generic file upload with metadata storage",
                "extensions": [".*"],
                "endpoint": "/upload/file"
            }
        }
    }
