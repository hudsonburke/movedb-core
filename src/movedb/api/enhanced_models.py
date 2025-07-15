"""Enhanced core models that bridge database and analysis functionality."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from uuid import UUID

import numpy as np
import polars as pl
from pydantic import BaseModel, ConfigDict, model_validator

from ..core.trial import Trial as BaseTrial
from ..core.events import Event as BaseEvent
from ..core.time_series import Points, Analogs
from ..core.force_platforms import EZForcePlatform as BaseForcePlatform

if TYPE_CHECKING:
    from .models import Trial as DBTrial, Event as DBEvent


class DatabaseMixin(BaseModel):
    """Mixin to add database fields to core models."""
    
    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )
    
    # Database fields (optional for core usage)
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EnhancedEvent(BaseEvent, DatabaseMixin):
    """Enhanced Event that can work with both database and core functionality."""
    
    trial_id: Optional[UUID] = None
    
    @classmethod
    def from_db(cls, db_event: "DBEvent") -> "EnhancedEvent":
        """Create from database model."""
        return cls(
            id=db_event.id,
            created_at=db_event.created_at,
            updated_at=db_event.updated_at,
            trial_id=db_event.trial_id,
            label=db_event.label,
            context=db_event.context,
            frame=db_event.frame,
            time=db_event.time,
            description=db_event.description,
        )
    
    def to_core(self) -> BaseEvent:
        """Convert to core Event model."""
        return BaseEvent(
            label=self.label,
            context=self.context,
            frame=self.frame,
            time=self.time,
            description=self.description,
        )


class EnhancedForcePlatform(BaseForcePlatform, DatabaseMixin):
    """Enhanced ForcePlatform that can work with both database and core functionality."""
    
    trial_id: Optional[UUID] = None
    
    @classmethod
    def from_db(cls, db_fp: "Any") -> "EnhancedForcePlatform":
        """Create from database model."""
        return cls(
            id=db_fp.id,
            created_at=db_fp.created_at,
            updated_at=db_fp.updated_at,
            trial_id=db_fp.trial_id,
            unit_force=db_fp.unit_force,
            unit_moment=db_fp.unit_moment,
            unit_position=db_fp.unit_position,
            cal_matrix=np.array(db_fp.cal_matrix),
            corners=np.array(db_fp.corners),
            origin=np.array(db_fp.origin),
            data=pl.DataFrame(db_fp.data) if db_fp.data else pl.DataFrame(),
        )
    
    def to_core(self) -> BaseForcePlatform:
        """Convert to core ForcePlatform model."""
        return BaseForcePlatform(
            unit_force=self.unit_force,
            unit_moment=self.unit_moment,
            unit_position=self.unit_position,
            cal_matrix=self.cal_matrix,
            corners=self.corners,
            origin=self.origin,
            data=self.data,
        )


class EnhancedTrial(BaseTrial, DatabaseMixin):
    """Enhanced Trial that can work with both database and core functionality."""
    
    # Override events and force_platforms with enhanced versions
    events: List[EnhancedEvent] = []
    force_platforms: List[EnhancedForcePlatform] = []
    
    @classmethod
    def from_db(cls, db_trial: "DBTrial") -> "EnhancedTrial":
        """Create from database model with all related data."""
        # This would be called by the service layer with full data loaded
        enhanced_events = [
            EnhancedEvent.from_db(event) for event in db_trial.events
        ]
        enhanced_fps = [
            EnhancedForcePlatform.from_db(fp) for fp in db_trial.force_platforms
        ]
        
        # Convert points and analogs from database JSON format
        points = None
        if db_trial.points_data:
            points = cls._db_points_to_core(db_trial.points_data)
            
        analogs = None
        if db_trial.analogs_data:
            analogs = cls._db_analogs_to_core(db_trial.analogs_data)
        
        trial_data = {
            'id': db_trial.id,
            'created_at': db_trial.created_at,
            'updated_at': db_trial.updated_at,
            'name': db_trial.name,
            'session_name': db_trial.session_name,
            'subject_names': db_trial.subject_names,
            'classification': db_trial.classification,
            'linked_files': db_trial.linked_files or {},
            'parameters': db_trial.parameters or {},
            'events': enhanced_events,
            'point_gaps': db_trial.point_gaps or {},
            'force_platforms': enhanced_fps,
        }
        
        if points:
            trial_data['points'] = points
        if analogs:
            trial_data['analogs'] = analogs
            
        return cls(**trial_data)
    
    def to_core(self) -> BaseTrial:
        """Convert to core Trial model."""
        core_events = [event.to_core() for event in self.events]
        core_fps = [fp.to_core() for fp in self.force_platforms]
        
        trial_data = {
            'name': self.name,
            'session_name': self.session_name,
            'subject_names': self.subject_names,
            'classification': self.classification,
            'linked_files': self.linked_files,
            'parameters': self.parameters,
            'events': core_events,
            'point_gaps': self.point_gaps,
            'force_platforms': core_fps,
        }
        
        if hasattr(self, 'points'):
            trial_data['points'] = self.points
        if hasattr(self, 'analogs'):
            trial_data['analogs'] = self.analogs
            
        return BaseTrial(**trial_data)
    
    @staticmethod
    def _db_points_to_core(db_points) -> Points:
        """Convert database PointsData to core Points."""
        from ..core.time_series import MarkerTrajectory
        
        trajectories = {}
        for name, traj_data in db_points.trajectories.items():
            df_data = traj_data['data']
            trajectory = MarkerTrajectory(
                data=pl.DataFrame(df_data),
                description=traj_data.get('description', ''),
            )
            trajectories[name] = trajectory

        return Points(
            first_frame=db_points.first_frame,
            last_frame=db_points.last_frame,
            rate=db_points.rate,
            units=db_points.units,
            trajectories=trajectories,
        )
    
    @staticmethod
    def _db_analogs_to_core(db_analogs) -> Analogs:
        """Convert database AnalogsData to core Analogs."""
        from ..core.time_series import AnalogChannel
        
        channels = {}
        for name, channel_data in db_analogs.channels.items():
            channel = AnalogChannel(
                data=channel_data['data'],
                units=channel_data.get('units', 'V'),
                scale=channel_data.get('scale', 1.0),
                offset=channel_data.get('offset', 0.0),
                description=channel_data.get('description', ''),
            )
            channels[name] = channel

        return Analogs(
            first_frame=db_analogs.first_frame,
            last_frame=db_analogs.last_frame,
            rate=db_analogs.rate,
            channels=channels,
            gen_scale=db_analogs.gen_scale,
        )
    
    # Enhanced methods that work with database context
    def save_to_db(self, session) -> UUID:
        """Save this enhanced trial to the database."""
        from .services import TrialService
        service = TrialService(session)
        core_trial = self.to_core()
        return service.core_to_db(core_trial)
    
    def update_in_db(self, session) -> None:
        """Update this trial in the database."""
        if not self.id:
            raise ValueError("Cannot update trial without ID")
        
        from .models import Trial as DBTrial
        db_trial = session.get(DBTrial, self.id)
        if not db_trial:
            raise ValueError(f"Trial with ID {self.id} not found")
        
        # Update basic fields
        db_trial.name = self.name
        db_trial.session_name = self.session_name
        db_trial.subject_names = self.subject_names
        db_trial.classification = self.classification
        db_trial.linked_files = self.linked_files
        db_trial.parameters = self.parameters
        db_trial.point_gaps = self.point_gaps
        db_trial.updated_at = datetime.utcnow()
        
        session.add(db_trial)
        session.commit()
    
    def delete_from_db(self, session) -> None:
        """Delete this trial from the database."""
        if not self.id:
            raise ValueError("Cannot delete trial without ID")
        
        from .models import Trial as DBTrial
        db_trial = session.get(DBTrial, self.id)
        if not db_trial:
            raise ValueError(f"Trial with ID {self.id} not found")
        
        session.delete(db_trial)
        session.commit()
    
    @classmethod
    def load_from_db(cls, session, trial_id: UUID) -> "EnhancedTrial":
        """Load an enhanced trial from the database."""
        from .services import TrialService
        service = TrialService(session)
        core_trial = service.db_to_core(trial_id)
        
        # Convert to enhanced trial
        # This is a simplified approach - in practice you'd want to preserve database metadata
        return cls.from_core_trial(core_trial, trial_id=trial_id)
    
    @classmethod
    def from_core_trial(cls, core_trial: BaseTrial, trial_id: Optional[UUID] = None) -> "EnhancedTrial":
        """Create enhanced trial from core trial."""
        enhanced_events = [
            EnhancedEvent(
                trial_id=trial_id,
                **event.model_dump()
            ) for event in core_trial.events
        ]
        
        enhanced_fps = [
            EnhancedForcePlatform(
                trial_id=trial_id,
                **fp.model_dump()
            ) for fp in core_trial.force_platforms
        ]
        
        trial_data = {
            'id': trial_id,
            'name': core_trial.name,
            'session_name': core_trial.session_name,
            'subject_names': core_trial.subject_names,
            'classification': core_trial.classification,
            'linked_files': core_trial.linked_files,
            'parameters': core_trial.parameters,
            'events': enhanced_events,
            'point_gaps': core_trial.point_gaps,
            'force_platforms': enhanced_fps,
        }
        
        if hasattr(core_trial, 'points'):
            trial_data['points'] = core_trial.points
        if hasattr(core_trial, 'analogs'):
            trial_data['analogs'] = core_trial.analogs
            
        return cls(**trial_data)


# Factory functions for easy conversion
def enhance_core_trial(core_trial: BaseTrial, trial_id: Optional[UUID] = None) -> EnhancedTrial:
    """Convert a core trial to an enhanced trial."""
    return EnhancedTrial.from_core_trial(core_trial, trial_id)


def load_enhanced_trial_from_db(session, trial_id: UUID) -> EnhancedTrial:
    """Load an enhanced trial from the database."""
    return EnhancedTrial.load_from_db(session, trial_id)


def create_enhanced_trial_from_c3d(c3d_path: str) -> EnhancedTrial:
    """Create an enhanced trial from a C3D file."""
    core_trial = BaseTrial.from_c3d_file(c3d_path)
    return enhance_core_trial(core_trial)
