"""Service layer for converting between core models and database models."""

from typing import Dict, List, Optional, Any
from uuid import UUID
import numpy as np
import polars as pl

from sqlmodel import Session, select
from ..core.trial import Trial as CoreTrial
from ..core.events import Event as CoreEvent
from ..core.time_series import Points, Analogs, MarkerTrajectory, AnalogChannel
from ..core.force_platforms import EZForcePlatform as CoreForcePlatform

from .models import (
    Trial, TrialCreate, TrialRead,
    Event, EventCreate, EventRead,
    ForcePlatform, ForcePlatformCreate, ForcePlatformRead,
    PointsData, PointsDataCreate, PointsDataRead,
    AnalogsData, AnalogsDataCreate, AnalogsDataRead,
    core_event_to_db, db_event_to_core,
    core_force_platform_to_db, db_force_platform_to_core,
)


class TrialService:
    """Service for handling trial operations between core and database models."""

    def __init__(self, session: Session):
        self.session = session

    def core_to_db(self, core_trial: CoreTrial) -> UUID:
        """
        Convert a core Trial to database models and save to database.
        Returns the UUID of the created trial.
        """
        # Create main trial record
        trial_create = TrialCreate(
            name=core_trial.name,
            session_name=core_trial.session_name,
            subject_names=core_trial.subject_names,
            classification=core_trial.classification,
            linked_files=core_trial.linked_files,
            parameters=core_trial.parameters,
            point_gaps=core_trial.point_gaps,
        )
        
        db_trial = Trial.model_validate(trial_create)
        self.session.add(db_trial)
        self.session.commit()
        self.session.refresh(db_trial)
        
        trial_id = db_trial.id

        # Add events
        for core_event in core_trial.events:
            event_create = core_event_to_db(core_event)
            db_event = Event.model_validate(event_create)
            db_event.trial_id = trial_id
            self.session.add(db_event)

        # Add force platforms
        for core_fp in core_trial.force_platforms:
            fp_create = core_force_platform_to_db(core_fp)
            db_fp = ForcePlatform.model_validate(fp_create)
            db_fp.trial_id = trial_id
            self.session.add(db_fp)

        # Add points data
        if hasattr(core_trial, 'points') and core_trial.points:
            points_create = self._core_points_to_db(core_trial.points)
            db_points = PointsData.model_validate(points_create)
            db_points.trial_id = trial_id
            self.session.add(db_points)

        # Add analogs data
        if hasattr(core_trial, 'analogs') and core_trial.analogs:
            analogs_create = self._core_analogs_to_db(core_trial.analogs)
            db_analogs = AnalogsData.model_validate(analogs_create)
            db_analogs.trial_id = trial_id
            self.session.add(db_analogs)

        self.session.commit()
        return trial_id

    def db_to_core(self, trial_id: UUID) -> CoreTrial:
        """
        Convert database models back to a core Trial.
        """
        # Get main trial
        db_trial = self.session.get(Trial, trial_id)
        if not db_trial:
            raise ValueError(f"Trial with ID {trial_id} not found")

        # Get related data
        events_stmt = select(Event).where(Event.trial_id == trial_id)
        db_events = self.session.exec(events_stmt).all()

        fp_stmt = select(ForcePlatform).where(ForcePlatform.trial_id == trial_id)
        db_force_platforms = self.session.exec(fp_stmt).all()

        points_stmt = select(PointsData).where(PointsData.trial_id == trial_id)
        db_points = self.session.exec(points_stmt).first()

        analogs_stmt = select(AnalogsData).where(AnalogsData.trial_id == trial_id)
        db_analogs = self.session.exec(analogs_stmt).first()

        # Convert to core objects
        core_events = [db_event_to_core(event) for event in db_events]
        core_force_platforms = [db_force_platform_to_core(fp) for fp in db_force_platforms]
        
        core_points = self._db_points_to_core(db_points) if db_points else None
        core_analogs = self._db_analogs_to_core(db_analogs) if db_analogs else None

        # Create core trial
        # Note: This requires some manual construction since CoreTrial expects specific types
        trial_data = {
            'name': db_trial.name,
            'session_name': db_trial.session_name,
            'subject_names': db_trial.subject_names,
            'classification': db_trial.classification,
            'linked_files': db_trial.linked_files or {},
            'parameters': db_trial.parameters or {},
            'events': core_events,
            'point_gaps': db_trial.point_gaps or {},
            'force_platforms': core_force_platforms,
        }

        if core_points:
            trial_data['points'] = core_points
        if core_analogs:
            trial_data['analogs'] = core_analogs

        return CoreTrial(**trial_data)

    def _core_points_to_db(self, core_points: Points) -> PointsDataCreate:
        """Convert core Points to database PointsData."""
        # Serialize trajectories to JSON-compatible format
        trajectories_data = {}
        for name, trajectory in core_points.trajectories.items():
            trajectories_data[name] = {
                'data': trajectory.data.to_dict(),
                'description': trajectory.description,
            }

        return PointsDataCreate(
            first_frame=core_points.first_frame,
            last_frame=core_points.last_frame,
            rate=core_points.rate,
            units=core_points.units,
            trajectories=trajectories_data,
        )

    def _db_points_to_core(self, db_points: PointsData) -> Points:
        """Convert database PointsData to core Points."""
        # Reconstruct trajectories from JSON data
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

    def _core_analogs_to_db(self, core_analogs: Analogs) -> AnalogsDataCreate:
        """Convert core Analogs to database AnalogsData."""
        # Serialize channels to JSON-compatible format
        channels_data = {}
        for name, channel in core_analogs.channels.items():
            channels_data[name] = {
                'data': channel.data,
                'units': channel.units,
                'scale': channel.scale,
                'offset': channel.offset,
                'description': channel.description,
            }

        return AnalogsDataCreate(
            first_frame=core_analogs.first_frame,
            last_frame=core_analogs.last_frame,
            rate=core_analogs.rate,
            units="V",  # Default for analogs
            channels=channels_data,
            gen_scale=core_analogs.gen_scale,
        )

    def _db_analogs_to_core(self, db_analogs: AnalogsData) -> Analogs:
        """Convert database AnalogsData to core Analogs."""
        # Reconstruct channels from JSON data
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


class BulkOperationService:
    """Service for bulk operations."""

    def __init__(self, session: Session):
        self.session = session

    def import_trials_from_c3d_directory(self, directory_path: str) -> List[UUID]:
        """
        Import all C3D files from a directory as trials.
        Returns list of created trial IDs.
        """
        import os
        trial_ids = []
        trial_service = TrialService(self.session)

        for filename in os.listdir(directory_path):
            if filename.lower().endswith('.c3d'):
                file_path = os.path.join(directory_path, filename)
                try:
                    core_trial = CoreTrial.from_c3d_file(file_path)
                    trial_id = trial_service.core_to_db(core_trial)
                    trial_ids.append(trial_id)
                except Exception as e:
                    print(f"Error importing {filename}: {e}")
                    continue

        return trial_ids

    def export_trial_to_formats(
        self,
        trial_id: UUID,
        output_dir: str,
        formats: List[str] = ['trc', 'mat', 'pkl']
    ) -> Dict[str, str]:
        """
        Export a trial to various formats.
        Returns dictionary of format -> file_path.
        """
        import os
        trial_service = TrialService(self.session)
        core_trial = trial_service.db_to_core(trial_id)
        
        exported_files = {}
        
        if 'trc' in formats:
            trc_path = os.path.join(output_dir, f"{core_trial.name}.trc")
            core_trial.to_trc(trc_path)
            exported_files['trc'] = trc_path
            
        if 'mat' in formats:
            mat_path = os.path.join(output_dir, f"{core_trial.name}.mat")
            core_trial.to_mat(mat_path)
            exported_files['mat'] = mat_path
            
        if 'pkl' in formats:
            pkl_path = os.path.join(output_dir, f"{core_trial.name}.pkl")
            core_trial.to_pkl(pkl_path)
            exported_files['pkl'] = pkl_path
            
        return exported_files


class AnalysisService:
    """Service for analysis operations on trials."""

    def __init__(self, session: Session):
        self.session = session

    def get_trial_statistics(self, trial_id: UUID) -> Dict[str, Any]:
        """Get basic statistics about a trial."""
        trial_service = TrialService(self.session)
        core_trial = trial_service.db_to_core(trial_id)
        
        stats = {
            'name': core_trial.name,
            'duration_frames': core_trial.points.total_frames if hasattr(core_trial, 'points') else 0,
            'duration_seconds': (core_trial.points.total_frames / core_trial.points.rate) if hasattr(core_trial, 'points') else 0,
            'num_events': len(core_trial.events),
            'num_force_platforms': len(core_trial.force_platforms),
            'num_markers': len(core_trial.points.trajectories) if hasattr(core_trial, 'points') else 0,
            'num_analog_channels': len(core_trial.analogs.channels) if hasattr(core_trial, 'analogs') else 0,
            'point_gaps': core_trial.point_gaps,
        }
        
        return stats

    def find_trials_with_gaps(self, marker_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find all trials that have marker gaps."""
        statement = select(Trial)
        trials = self.session.exec(statement).all()
        
        trials_with_gaps = []
        trial_service = TrialService(self.session)
        
        for db_trial in trials:
            try:
                core_trial = trial_service.db_to_core(db_trial.id)
                gaps = core_trial.check_point_gaps()
                
                if marker_name:
                    if marker_name in gaps and gaps[marker_name]:
                        trials_with_gaps.append({
                            'trial_id': str(db_trial.id),
                            'trial_name': db_trial.name,
                            'gaps': {marker_name: gaps[marker_name]}
                        })
                else:
                    if any(gap_list for gap_list in gaps.values()):
                        trials_with_gaps.append({
                            'trial_id': str(db_trial.id),
                            'trial_name': db_trial.name,
                            'gaps': gaps
                        })
            except Exception as e:
                continue  # Skip trials that can't be loaded
                
        return trials_with_gaps
