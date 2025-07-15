"""SQLModel definitions for database storage."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, Relationship, JSON
from sqlalchemy import Text, DateTime
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from pydantic import BaseModel, ConfigDict

from ..core.events import Event as CoreEvent
from ..core.time_series import TimeSeriesGroup, MarkerTrajectory, AnalogChannel
from ..core.force_platforms import EZForcePlatform as CoreForcePlatform


class BaseTable(SQLModel):
    """Base table class with common fields."""
    
    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column=Column(PostgresUUID(as_uuid=True), primary_key=True)
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True))
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True))
    )


class CoreBaseModel(BaseModel):
    """Base model for core analysis classes that mirrors SQLModel structure."""
    
    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )
    
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Event Models
class EventBase(SQLModel):
    """Base event model."""
    label: str = Field(max_length=100)
    context: str = Field(max_length=100)
    frame: Optional[int] = None
    time: Optional[float] = None
    description: Optional[str] = Field(default=None, sa_column=Column(Text))


class Event(EventBase, BaseTable, table=True):
    """Database event model."""
    __tablename__ = "events"
    
    trial_id: Optional[UUID] = Field(
        default=None,
        foreign_key="trials.id",
        sa_column=Column(PostgresUUID(as_uuid=True))
    )
    
    # Relationships
    trial: Optional["Trial"] = Relationship(back_populates="events")


class EventRead(EventBase):
    """Event model for API responses."""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    trial_id: Optional[UUID] = None


class EventCreate(EventBase):
    """Event model for API creation."""
    pass


class EventUpdate(SQLModel):
    """Event model for API updates."""
    label: Optional[str] = None
    context: Optional[str] = None
    frame: Optional[int] = None
    time: Optional[float] = None
    description: Optional[str] = None


# Force Platform Models
class ForcePlatformBase(SQLModel):
    """Base force platform model."""
    unit_force: str = Field(default="N", max_length=10)
    unit_moment: str = Field(default="Nm", max_length=10)
    unit_position: str = Field(default="m", max_length=10)
    cal_matrix: List[List[float]] = Field(default_factory=lambda: [[1.0]*6 for _ in range(6)], sa_column=Column(JSON))
    corners: List[List[float]] = Field(default_factory=lambda: [[0.0]*3 for _ in range(4)], sa_column=Column(JSON))
    origin: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], sa_column=Column(JSON))
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class ForcePlatform(ForcePlatformBase, BaseTable, table=True):
    """Database force platform model."""
    __tablename__ = "force_platforms"
    
    trial_id: Optional[UUID] = Field(
        default=None,
        foreign_key="trials.id",
        sa_column=Column(PostgresUUID(as_uuid=True))
    )
    
    # Relationships
    trial: Optional["Trial"] = Relationship(back_populates="force_platforms")


class ForcePlatformRead(ForcePlatformBase):
    """Force platform model for API responses."""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    trial_id: Optional[UUID] = None


class ForcePlatformCreate(ForcePlatformBase):
    """Force platform model for API creation."""
    pass


class ForcePlatformUpdate(SQLModel):
    """Force platform model for API updates."""
    unit_force: Optional[str] = None
    unit_moment: Optional[str] = None
    unit_position: Optional[str] = None
    cal_matrix: Optional[List[List[float]]] = None
    corners: Optional[List[List[float]]] = None
    origin: Optional[List[float]] = None
    data: Optional[Dict[str, Any]] = None


# Time Series Models
class TimeSeriesBase(SQLModel):
    """Base time series model."""
    first_frame: int = Field(ge=0)
    last_frame: int
    rate: float = Field(gt=0)
    units: str = Field(default="mm", max_length=10)


class PointsData(TimeSeriesBase, BaseTable, table=True):
    """Database points/marker data model."""
    __tablename__ = "points_data"
    
    trial_id: Optional[UUID] = Field(
        default=None,
        foreign_key="trials.id",
        sa_column=Column(PostgresUUID(as_uuid=True))
    )
    
    # Store trajectories as JSON
    trajectories: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Relationships
    trial: Optional["Trial"] = Relationship(back_populates="points_data")


class PointsDataRead(TimeSeriesBase):
    """Points data model for API responses."""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    trial_id: Optional[UUID] = None
    trajectories: Dict[str, Any]


class PointsDataCreate(TimeSeriesBase):
    """Points data model for API creation."""
    trajectories: Dict[str, Any] = Field(default_factory=dict)


class PointsDataUpdate(SQLModel):
    """Points data model for API updates."""
    first_frame: Optional[int] = None
    last_frame: Optional[int] = None
    rate: Optional[float] = None
    units: Optional[str] = None
    trajectories: Optional[Dict[str, Any]] = None


class AnalogsData(TimeSeriesBase, BaseTable, table=True):
    """Database analog data model."""
    __tablename__ = "analogs_data"
    
    trial_id: Optional[UUID] = Field(
        default=None,
        foreign_key="trials.id",
        sa_column=Column(PostgresUUID(as_uuid=True))
    )
    
    # Store channels as JSON
    channels: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    gen_scale: float = Field(default=1.0)
    
    # Relationships
    trial: Optional["Trial"] = Relationship(back_populates="analogs_data")


class AnalogsDataRead(TimeSeriesBase):
    """Analogs data model for API responses."""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    trial_id: Optional[UUID] = None
    channels: Dict[str, Any]
    gen_scale: float


class AnalogsDataCreate(TimeSeriesBase):
    """Analogs data model for API creation."""
    channels: Dict[str, Any] = Field(default_factory=dict)
    gen_scale: float = Field(default=1.0)


class AnalogsDataUpdate(SQLModel):
    """Analogs data model for API updates."""
    first_frame: Optional[int] = None
    last_frame: Optional[int] = None
    rate: Optional[float] = None
    units: Optional[str] = None
    channels: Optional[Dict[str, Any]] = None
    gen_scale: Optional[float] = None


# Trial Models
class TrialBase(SQLModel):
    """Base trial model."""
    name: str = Field(max_length=255)
    session_name: Optional[str] = Field(default=None, max_length=255)
    subject_names: Union[List[str], str, None] = Field(default=None, sa_column=Column(JSON))
    classification: str = Field(default="", max_length=100)
    linked_files: Dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    parameters: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    point_gaps: Dict[str, List[List[int]]] = Field(default_factory=dict, sa_column=Column(JSON))


class Trial(TrialBase, BaseTable, table=True):
    """Database trial model."""
    __tablename__ = "trials"
    
    # Relationships
    events: List["Event"] = Relationship(back_populates="trial")
    force_platforms: List["ForcePlatform"] = Relationship(back_populates="trial")
    points_data: Optional["PointsData"] = Relationship(back_populates="trial")
    analogs_data: Optional["AnalogsData"] = Relationship(back_populates="trial")


class TrialRead(TrialBase):
    """Trial model for API responses."""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Related data
    events: List[EventRead] = []
    force_platforms: List[ForcePlatformRead] = []
    points_data: Optional[PointsDataRead] = None
    analogs_data: Optional[AnalogsDataRead] = None


class TrialCreate(TrialBase):
    """Trial model for API creation."""
    pass


class TrialUpdate(SQLModel):
    """Trial model for API updates."""
    name: Optional[str] = None
    session_name: Optional[str] = None
    subject_names: Optional[Union[List[str], str, None]] = None
    classification: Optional[str] = None
    linked_files: Optional[Dict[str, str]] = None
    parameters: Optional[Dict[str, Any]] = None
    point_gaps: Optional[Dict[str, List[List[int]]]] = None


# Enhanced Core Models that inherit from CoreBaseModel
class CoreTrialEnhanced(CoreBaseModel):
    """Enhanced core trial model that includes database fields."""
    
    # Trial Metadata
    name: str
    session_name: Optional[str] = None
    subject_names: Union[List[str], str, None] = None
    classification: str = ""
    linked_files: Dict[str, str] = {}
    parameters: Dict[str, Any] = {}
    point_gaps: Dict[str, List[List[int]]] = {}
    
    # Core analysis fields (these would be populated from core classes)
    events: List[CoreEvent] = []
    # Note: points, analogs, and force_platforms would be handled separately
    # as they require special handling for the complex data structures


class CoreEventEnhanced(CoreBaseModel, CoreEvent):
    """Enhanced core event model that includes database fields."""
    pass


# Conversion utilities
def core_event_to_db(core_event: CoreEvent) -> EventCreate:
    """Convert core Event to database Event."""
    return EventCreate(
        label=core_event.label,
        context=core_event.context,
        frame=core_event.frame,
        time=core_event.time,
        description=core_event.description
    )


def db_event_to_core(db_event: Event) -> CoreEvent:
    """Convert database Event to core Event."""
    return CoreEvent(
        label=db_event.label,
        context=db_event.context,
        frame=db_event.frame,
        time=db_event.time,
        description=db_event.description
    )


def core_force_platform_to_db(core_fp: CoreForcePlatform) -> ForcePlatformCreate:
    """Convert core ForcePlatform to database ForcePlatform."""
    import numpy as np
    
    return ForcePlatformCreate(
        unit_force=core_fp.unit_force,
        unit_moment=core_fp.unit_moment,
        unit_position=core_fp.unit_position,
        cal_matrix=core_fp.cal_matrix.tolist(),
        corners=core_fp.corners.tolist(),
        origin=core_fp.origin.tolist(),
        data=core_fp.data.to_dict() if hasattr(core_fp.data, 'to_dict') else {}
    )


def db_force_platform_to_core(db_fp: ForcePlatform) -> CoreForcePlatform:
    """Convert database ForcePlatform to core ForcePlatform."""
    import numpy as np
    import polars as pl
    
    return CoreForcePlatform(
        unit_force=db_fp.unit_force,
        unit_moment=db_fp.unit_moment,
        unit_position=db_fp.unit_position,
        cal_matrix=np.array(db_fp.cal_matrix),
        corners=np.array(db_fp.corners),
        origin=np.array(db_fp.origin),
        data=pl.DataFrame(db_fp.data) if db_fp.data else pl.DataFrame()
    )
