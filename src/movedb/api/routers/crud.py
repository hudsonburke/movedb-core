from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, col
from typing import Any, Optional
from ..dependencies import SessionDep
from ...models import (
    Trial, Marker, MarkerData, Analog, AnalogData, 
    ForcePlate, ForcePlateData, Event, CaptureSession, 
    Subject, TrialGroup, File
)

# Create individual routers for each model
router = APIRouter(prefix="/api/v1", tags=["CRUD Operations"])

# Trial endpoints
@router.get("/trials", response_model=list[Trial])
def get_trials(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    name: Optional[str] = Query(None, description="Filter by trial name")
):
    """Get all trials with optional filtering and pagination."""
    query = select(Trial)
    if name:
        query = query.where(col(Trial.name).like(f"%{name}%"))
    trials = session.exec(query.offset(skip).limit(limit)).all()
    return trials

@router.get("/trials/{trial_id}", response_model=Trial)
def get_trial(trial_id: int, session: SessionDep):
    """Get a specific trial by ID."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    return trial

@router.post("/trials", response_model=Trial)
def create_trial(trial: Trial, session: SessionDep):
    """Create a new trial."""
    session.add(trial)
    session.commit()
    session.refresh(trial)
    return trial

@router.put("/trials/{trial_id}", response_model=Trial)
def update_trial(trial_id: int, trial_update: Trial, session: SessionDep):
    """Update an existing trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    trial_data = trial_update.model_dump(exclude_unset=True)
    for key, value in trial_data.items():
        setattr(trial, key, value)
    
    session.add(trial)
    session.commit()
    session.refresh(trial)
    return trial

@router.delete("/trials/{trial_id}")
def delete_trial(trial_id: int, session: SessionDep):
    """Delete a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    session.delete(trial)
    session.commit()
    return {"message": "Trial deleted successfully"}

# Marker endpoints
@router.get("/trials/{trial_id}/markers", response_model=list[Marker])
def get_trial_markers(trial_id: int, session: SessionDep):
    """Get all markers for a specific trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    return trial.markers

@router.get("/markers/{marker_id}", response_model=Marker)
def get_marker(marker_id: int, session: SessionDep):
    """Get a specific marker by ID."""
    marker = session.get(Marker, marker_id)
    if not marker:
        raise HTTPException(status_code=404, detail="Marker not found")
    return marker

@router.post("/trials/{trial_id}/markers", response_model=Marker)
def create_marker(trial_id: int, marker: Marker, session: SessionDep):
    """Create a new marker for a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    marker.trial_id = trial_id
    session.add(marker)
    session.commit()
    session.refresh(marker)
    return marker

# Analog endpoints
@router.get("/trials/{trial_id}/analogs", response_model=list[Analog])
def get_trial_analogs(trial_id: int, session: SessionDep):
    """Get all analog channels for a specific trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    return trial.analogs

@router.get("/analogs/{analog_id}", response_model=Analog)
def get_analog(analog_id: int, session: SessionDep):
    """Get a specific analog channel by ID."""
    analog = session.get(Analog, analog_id)
    if not analog:
        raise HTTPException(status_code=404, detail="Analog channel not found")
    return analog

@router.post("/trials/{trial_id}/analogs", response_model=Analog)
def create_analog(trial_id: int, analog: Analog, session: SessionDep):
    """Create a new analog channel for a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    analog.trial_id = trial_id
    session.add(analog)
    session.commit()
    session.refresh(analog)
    return analog

# Force plate endpoints
@router.get("/trials/{trial_id}/forceplates", response_model=list[ForcePlate])
def get_trial_forceplates(trial_id: int, session: SessionDep):
    """Get all force plates for a specific trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    return trial.forceplates

@router.get("/forceplates/{forceplate_id}", response_model=ForcePlate)
def get_forceplate(forceplate_id: int, session: SessionDep):
    """Get a specific force plate by ID."""
    forceplate = session.get(ForcePlate, forceplate_id)
    if not forceplate:
        raise HTTPException(status_code=404, detail="Force plate not found")
    return forceplate

@router.post("/trials/{trial_id}/forceplates", response_model=ForcePlate)
def create_forceplate(trial_id: int, forceplate: ForcePlate, session: SessionDep):
    """Create a new force plate for a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    forceplate.trial_id = trial_id
    session.add(forceplate)
    session.commit()
    session.refresh(forceplate)
    return forceplate

# Event endpoints
@router.get("/trials/{trial_id}/events", response_model=list[Event])
def get_trial_events(trial_id: int, session: SessionDep):
    """Get all events for a specific trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    return trial.events

@router.get("/events/{event_id}", response_model=Event)
def get_event(event_id: int, session: SessionDep):
    """Get a specific event by ID."""
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.post("/trials/{trial_id}/events", response_model=Event)
def create_event(trial_id: int, event: Event, session: SessionDep):
    """Create a new event for a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    event.trial_id = trial_id
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

# Capture Session endpoints
@router.get("/capture-sessions", response_model=list[CaptureSession])
def get_capture_sessions(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get all capture sessions with pagination."""
    sessions = session.exec(select(CaptureSession).offset(skip).limit(limit)).all()
    return sessions

@router.get("/capture-sessions/{session_id}", response_model=CaptureSession)
def get_capture_session(session_id: int, session: SessionDep):
    """Get a specific capture session by ID."""
    capture_session = session.get(CaptureSession, session_id)
    if not capture_session:
        raise HTTPException(status_code=404, detail="Capture session not found")
    return capture_session

@router.post("/capture-sessions", response_model=CaptureSession)
def create_capture_session(capture_session: CaptureSession, session: SessionDep):
    """Create a new capture session."""
    session.add(capture_session)
    session.commit()
    session.refresh(capture_session)
    return capture_session

# Subject endpoints
@router.get("/subjects", response_model=list[Subject])
def get_subjects(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get all subjects with pagination."""
    subjects = session.exec(select(Subject).offset(skip).limit(limit)).all()
    return subjects

@router.get("/subjects/{subject_id}", response_model=Subject)
def get_subject(subject_id: int, session: SessionDep):
    """Get a specific subject by ID."""
    subject = session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject

@router.post("/subjects", response_model=Subject)
def create_subject(subject: Subject, session: SessionDep):
    """Create a new subject."""
    session.add(subject)
    session.commit()
    session.refresh(subject)
    return subject
