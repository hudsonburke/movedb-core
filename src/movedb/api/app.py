"""FastAPI application for MoveDB Core."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from .database import engine
from .models import (
    Trial, TrialRead, TrialCreate, TrialUpdate,
    Event, EventRead, EventCreate, EventUpdate,
    ForcePlatform, ForcePlatformRead, ForcePlatformCreate, ForcePlatformUpdate,
    PointsData, PointsDataRead, PointsDataCreate, PointsDataUpdate,
    AnalogsData, AnalogsDataRead, AnalogsDataCreate, AnalogsDataUpdate,
)

# Create FastAPI app
app = FastAPI(
    title="MoveDB Core API",
    description="API for biomechanical trial data storage and retrieval",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get database session
def get_session():
    with Session(engine) as session:
        yield session


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


# Trial endpoints
@app.post("/trials/", response_model=TrialRead)
def create_trial(trial: TrialCreate, session: Session = Depends(get_session)):
    """Create a new trial."""
    db_trial = Trial.model_validate(trial)
    session.add(db_trial)
    session.commit()
    session.refresh(db_trial)
    return db_trial


@app.get("/trials/", response_model=List[TrialRead])
def read_trials(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_session)
):
    """Get all trials with pagination."""
    statement = (
        select(Trial)
        .options(
            selectinload(Trial.events),
            selectinload(Trial.force_platforms),
            selectinload(Trial.points_data),
            selectinload(Trial.analogs_data),
        )
        .offset(skip)
        .limit(limit)
    )
    trials = session.exec(statement).all()
    return trials


@app.get("/trials/{trial_id}", response_model=TrialRead)
def read_trial(trial_id: UUID, session: Session = Depends(get_session)):
    """Get a specific trial by ID."""
    statement = (
        select(Trial)
        .options(
            selectinload(Trial.events),
            selectinload(Trial.force_platforms),
            selectinload(Trial.points_data),
            selectinload(Trial.analogs_data),
        )
        .where(Trial.id == trial_id)
    )
    trial = session.exec(statement).first()
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    return trial


@app.put("/trials/{trial_id}", response_model=TrialRead)
def update_trial(
    trial_id: UUID,
    trial_update: TrialUpdate,
    session: Session = Depends(get_session)
):
    """Update a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    trial_data = trial_update.model_dump(exclude_unset=True)
    for field, value in trial_data.items():
        setattr(trial, field, value)
    
    trial.updated_at = datetime.utcnow()
    session.add(trial)
    session.commit()
    session.refresh(trial)
    return trial


@app.delete("/trials/{trial_id}")
def delete_trial(trial_id: UUID, session: Session = Depends(get_session)):
    """Delete a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    session.delete(trial)
    session.commit()
    return {"message": "Trial deleted successfully"}


# Event endpoints
@app.post("/trials/{trial_id}/events/", response_model=EventRead)
def create_event(
    trial_id: UUID,
    event: EventCreate,
    session: Session = Depends(get_session)
):
    """Create a new event for a trial."""
    # Verify trial exists
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    db_event = Event.model_validate(event)
    db_event.trial_id = trial_id
    session.add(db_event)
    session.commit()
    session.refresh(db_event)
    return db_event


@app.get("/trials/{trial_id}/events/", response_model=List[EventRead])
def read_trial_events(
    trial_id: UUID,
    label: Optional[str] = None,
    context: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Get all events for a trial, optionally filtered by label and context."""
    statement = select(Event).where(Event.trial_id == trial_id)
    
    if label:
        statement = statement.where(Event.label == label)
    if context:
        statement = statement.where(Event.context == context)
    
    events = session.exec(statement).all()
    return events


@app.get("/events/{event_id}", response_model=EventRead)
def read_event(event_id: UUID, session: Session = Depends(get_session)):
    """Get a specific event by ID."""
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.put("/events/{event_id}", response_model=EventRead)
def update_event(
    event_id: UUID,
    event_update: EventUpdate,
    session: Session = Depends(get_session)
):
    """Update an event."""
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event_data = event_update.model_dump(exclude_unset=True)
    for field, value in event_data.items():
        setattr(event, field, value)
    
    event.updated_at = datetime.utcnow()
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@app.delete("/events/{event_id}")
def delete_event(event_id: UUID, session: Session = Depends(get_session)):
    """Delete an event."""
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    session.delete(event)
    session.commit()
    return {"message": "Event deleted successfully"}


# Force Platform endpoints
@app.post("/trials/{trial_id}/force-platforms/", response_model=ForcePlatformRead)
def create_force_platform(
    trial_id: UUID,
    force_platform: ForcePlatformCreate,
    session: Session = Depends(get_session)
):
    """Create a new force platform for a trial."""
    # Verify trial exists
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    db_fp = ForcePlatform.model_validate(force_platform)
    db_fp.trial_id = trial_id
    session.add(db_fp)
    session.commit()
    session.refresh(db_fp)
    return db_fp


@app.get("/trials/{trial_id}/force-platforms/", response_model=List[ForcePlatformRead])
def read_trial_force_platforms(
    trial_id: UUID,
    session: Session = Depends(get_session)
):
    """Get all force platforms for a trial."""
    statement = select(ForcePlatform).where(ForcePlatform.trial_id == trial_id)
    force_platforms = session.exec(statement).all()
    return force_platforms


@app.get("/force-platforms/{fp_id}", response_model=ForcePlatformRead)
def read_force_platform(fp_id: UUID, session: Session = Depends(get_session)):
    """Get a specific force platform by ID."""
    fp = session.get(ForcePlatform, fp_id)
    if not fp:
        raise HTTPException(status_code=404, detail="Force platform not found")
    return fp


@app.put("/force-platforms/{fp_id}", response_model=ForcePlatformRead)
def update_force_platform(
    fp_id: UUID,
    fp_update: ForcePlatformUpdate,
    session: Session = Depends(get_session)
):
    """Update a force platform."""
    fp = session.get(ForcePlatform, fp_id)
    if not fp:
        raise HTTPException(status_code=404, detail="Force platform not found")
    
    fp_data = fp_update.model_dump(exclude_unset=True)
    for field, value in fp_data.items():
        setattr(fp, field, value)
    
    fp.updated_at = datetime.utcnow()
    session.add(fp)
    session.commit()
    session.refresh(fp)
    return fp


@app.delete("/force-platforms/{fp_id}")
def delete_force_platform(fp_id: UUID, session: Session = Depends(get_session)):
    """Delete a force platform."""
    fp = session.get(ForcePlatform, fp_id)
    if not fp:
        raise HTTPException(status_code=404, detail="Force platform not found")
    
    session.delete(fp)
    session.commit()
    return {"message": "Force platform deleted successfully"}


# Points Data endpoints
@app.post("/trials/{trial_id}/points/", response_model=PointsDataRead)
def create_points_data(
    trial_id: UUID,
    points: PointsDataCreate,
    session: Session = Depends(get_session)
):
    """Create points data for a trial."""
    # Verify trial exists
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    db_points = PointsData.model_validate(points)
    db_points.trial_id = trial_id
    session.add(db_points)
    session.commit()
    session.refresh(db_points)
    return db_points


@app.get("/trials/{trial_id}/points/", response_model=Optional[PointsDataRead])
def read_trial_points_data(
    trial_id: UUID,
    session: Session = Depends(get_session)
):
    """Get points data for a trial."""
    statement = select(PointsData).where(PointsData.trial_id == trial_id)
    points = session.exec(statement).first()
    return points


@app.put("/points/{points_id}", response_model=PointsDataRead)
def update_points_data(
    points_id: UUID,
    points_update: PointsDataUpdate,
    session: Session = Depends(get_session)
):
    """Update points data."""
    points = session.get(PointsData, points_id)
    if not points:
        raise HTTPException(status_code=404, detail="Points data not found")
    
    points_data = points_update.model_dump(exclude_unset=True)
    for field, value in points_data.items():
        setattr(points, field, value)
    
    points.updated_at = datetime.utcnow()
    session.add(points)
    session.commit()
    session.refresh(points)
    return points


# Analogs Data endpoints
@app.post("/trials/{trial_id}/analogs/", response_model=AnalogsDataRead)
def create_analogs_data(
    trial_id: UUID,
    analogs: AnalogsDataCreate,
    session: Session = Depends(get_session)
):
    """Create analogs data for a trial."""
    # Verify trial exists
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    db_analogs = AnalogsData.model_validate(analogs)
    db_analogs.trial_id = trial_id
    session.add(db_analogs)
    session.commit()
    session.refresh(db_analogs)
    return db_analogs


@app.get("/trials/{trial_id}/analogs/", response_model=Optional[AnalogsDataRead])
def read_trial_analogs_data(
    trial_id: UUID,
    session: Session = Depends(get_session)
):
    """Get analogs data for a trial."""
    statement = select(AnalogsData).where(AnalogsData.trial_id == trial_id)
    analogs = session.exec(statement).first()
    return analogs


@app.put("/analogs/{analogs_id}", response_model=AnalogsDataRead)
def update_analogs_data(
    analogs_id: UUID,
    analogs_update: AnalogsDataUpdate,
    session: Session = Depends(get_session)
):
    """Update analogs data."""
    analogs = session.get(AnalogsData, analogs_id)
    if not analogs:
        raise HTTPException(status_code=404, detail="Analogs data not found")
    
    analogs_data = analogs_update.model_dump(exclude_unset=True)
    for field, value in analogs_data.items():
        setattr(analogs, field, value)
    
    analogs.updated_at = datetime.utcnow()
    session.add(analogs)
    session.commit()
    session.refresh(analogs)
    return analogs


# Search and query endpoints
@app.get("/trials/search/", response_model=List[TrialRead])
def search_trials(
    name: Optional[str] = None,
    session_name: Optional[str] = None,
    classification: Optional[str] = None,
    subject_name: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_session)
):
    """Search trials by various criteria."""
    statement = select(Trial)
    
    if name:
        statement = statement.where(Trial.name.ilike(f"%{name}%"))
    if session_name:
        statement = statement.where(Trial.session_name.ilike(f"%{session_name}%"))
    if classification:
        statement = statement.where(Trial.classification.ilike(f"%{classification}%"))
    if subject_name:
        # This is a simplified search - in practice you might want to use JSON operators
        statement = statement.where(Trial.subject_names.contains(subject_name))
    
    statement = statement.offset(skip).limit(limit)
    trials = session.exec(statement).all()
    return trials


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
