"""
API plotting service that wraps the core plotting module for web endpoints.

This service provides a thin layer over the core plotting functions,
ensuring they return JSON for API consumption.
"""

from typing import Dict, List, Optional, Any, cast
from sqlmodel import Session
from ...plot import (
    plot_marker_trajectory_3d,
    plot_force_plate_timeseries,
    plot_analog_signals,
    plot_gait_analysis,
    plot_trial_dashboard,
    plot_3d_trial_visualizer,
    get_trial_time_range,
    get_plot_config
)


class BiomechanicalPlotService:
    """API service for generating consistent biomechanical plots."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_marker_trajectory_3d(
        self, 
        trial_id: int, 
        marker_names: Optional[List[str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """Generate 3D marker trajectory plot configuration for API."""
        return cast(Dict[str, Any], plot_marker_trajectory_3d(
            session=self.session,
            trial_id=trial_id,
            marker_names=marker_names,
            start_time=start_time,
            end_time=end_time,
            return_json=True
        ))
    
    def get_force_plate_timeseries(
        self,
        trial_id: int,
        force_plate_ids: Optional[List[int]] = None,
        components: List[str] = ['force_x', 'force_y', 'force_z'],
        normalize_time: bool = True
    ) -> Dict[str, Any]:
        """Generate force plate time series plot configuration for API."""
        return cast(Dict[str, Any], plot_force_plate_timeseries(
            session=self.session,
            trial_id=trial_id,
            force_plate_ids=force_plate_ids,
            components=components,
            normalize_time=normalize_time,
            return_json=True
        ))
    
    def get_analog_signals(
        self,
        trial_id: int,
        analog_names: Optional[List[str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        normalize_time: bool = True
    ) -> Dict[str, Any]:
        """Generate analog signals plot configuration for API."""
        return cast(Dict[str, Any], plot_analog_signals(
            session=self.session,
            trial_id=trial_id,
            analog_names=analog_names,
            start_time=start_time,
            end_time=end_time,
            normalize_time=normalize_time,
            return_json=True
        ))
    
    def get_gait_analysis(
        self,
        trial_id: int,
        marker_name: str = "HEEL",
        axis: str = "z",
        detect_events: bool = True
    ) -> Dict[str, Any]:
        """Generate gait analysis plot configuration for API."""
        return cast(Dict[str, Any], plot_gait_analysis(
            session=self.session,
            trial_id=trial_id,
            marker_name=marker_name,
            axis=axis,
            detect_events=detect_events,
            return_json=True
        ))
    
    def get_trial_dashboard(self, trial_id: int) -> Dict[str, Any]:
        """Generate trial dashboard configuration for API."""
        return cast(Dict[str, Any], plot_trial_dashboard(
            session=self.session,
            trial_id=trial_id,
            return_json=True
        ))

    def get_3d_trial_visualizer(
        self,
        trial_id: int,
        current_time: float = 0.0,
        time_window: float = 0.1,
        show_force_plates: bool = True,
        show_force_vectors: bool = True,
        show_markers: bool = True,
        show_trajectories: bool = True,
        trajectory_length: float = 1.0,
        force_scale: float = 0.001,
        marker_size: int = 8
    ) -> Dict[str, Any]:
        """Generate 3D trial visualizer configuration for API."""
        return cast(Dict[str, Any], plot_3d_trial_visualizer(
            session=self.session,
            trial_id=trial_id,
            current_time=current_time,
            time_window=time_window,
            show_force_plates=show_force_plates,
            show_force_vectors=show_force_vectors,
            show_markers=show_markers,
            show_trajectories=show_trajectories,
            trajectory_length=trajectory_length,
            force_scale=force_scale,
            marker_size=marker_size,
            return_json=True
        ))

    def get_trial_time_range(self, trial_id: int) -> Dict[str, Any]:
        """Get trial time range for API."""
        return get_trial_time_range(
            session=self.session,
            trial_id=trial_id
        )

    def get_custom_plot_config(self) -> Dict[str, Any]:
        """Get the standard plot configuration for frontend applications."""
        return get_plot_config()
