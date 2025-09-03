from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from typing import Any, Optional, Literal, List, Dict
import pandas as pd
import numpy as np
from ..dependencies import SessionDep
from ...models import Trial, Marker, Analog, ForcePlate
from ..services.plotting import BiomechanicalPlotService

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"]
)

@router.get("/trials/{trial_id}/summary")
def get_trial_summary(trial_id: int, session: SessionDep):
    """Get a comprehensive summary of trial data."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    summary = {
        "trial_info": {
            "id": trial.id,
            "name": trial.name,
            "description": trial.description,
            "rate": trial.rate,
            "first_frame": trial.first_frame,
            "last_frame": trial.last_frame,
            "duration_frames": trial.last_frame - trial.first_frame if trial.last_frame else None,
            "duration_seconds": (trial.last_frame - trial.first_frame) / trial.rate if trial.last_frame and trial.rate else None
        },
        "data_counts": {
            "markers": len(trial.markers),
            "analogs": len(trial.analogs),
            "forceplates": len(trial.forceplates),
            "events": len(trial.events)
        },
        "marker_list": [{"id": m.id, "name": m.name, "units": m.units} for m in trial.markers],
        "analog_list": [{"id": a.id, "name": a.name, "units": a.units} for a in trial.analogs],
        "forceplate_list": [{"id": fp.id, "name": fp.name} for fp in trial.forceplates],
        "event_list": [{"id": e.id, "label": e.label, "context": e.context, "frame": e.frame} for e in trial.events]
    }
    
    return summary

@router.get("/trials/{trial_id}/markers/{marker_id}/data")
def get_marker_data(
    trial_id: int, 
    marker_id: int, 
    session: SessionDep,
    format: Literal["json", "csv"] = Query("json", description="Output format"),
    start_frame: Optional[int] = Query(None, description="Start frame (inclusive)"),
    end_frame: Optional[int] = Query(None, description="End frame (inclusive)")
):
    """Get marker trajectory data."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    marker = session.get(Marker, marker_id)
    if not marker or marker.trial_id != trial_id:
        raise HTTPException(status_code=404, detail="Marker not found in this trial")
    
    # Get marker data using the cached property
    df = marker.to_pandas
    
    if df.empty:
        return {"message": "No data available for this marker"}
    
    # Apply frame filtering if specified
    if start_frame is not None or end_frame is not None:
        # Convert timestamp to frame numbers (assuming consistent sampling rate)
        frame_duration = 1.0 / trial.rate if trial.rate else 1.0
        df['frame'] = (df.index.total_seconds() / frame_duration).astype(int) + trial.first_frame
        
        if start_frame is not None:
            df = df[df['frame'] >= start_frame]
        if end_frame is not None:
            df = df[df['frame'] <= end_frame]
    
    if format == "csv":
        return {"csv_data": df.to_csv()}
    else:
        return {
            "marker_info": {
                "id": marker.id,
                "name": marker.name,
                "units": marker.units
            },
            "data": df.to_dict('records')
        }

@router.get("/trials/{trial_id}/analogs/{analog_id}/data")
def get_analog_data(
    trial_id: int, 
    analog_id: int, 
    session: SessionDep,
    format: Literal["json", "csv"] = Query("json", description="Output format"),
    start_frame: Optional[int] = Query(None, description="Start frame (inclusive)"),
    end_frame: Optional[int] = Query(None, description="End frame (inclusive)")
):
    """Get analog channel data."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    analog = session.get(Analog, analog_id)
    if not analog or analog.trial_id != trial_id:
        raise HTTPException(status_code=404, detail="Analog channel not found in this trial")
    
    # Get analog data using the cached property
    df = analog.to_pandas
    
    if df.empty:
        return {"message": "No data available for this analog channel"}
    
    # Apply frame filtering if specified
    if start_frame is not None or end_frame is not None:
        frame_duration = 1.0 / trial.rate if trial.rate else 1.0
        df['frame'] = (df.index.total_seconds() / frame_duration).astype(int) + trial.first_frame
        
        if start_frame is not None:
            df = df[df['frame'] >= start_frame]
        if end_frame is not None:
            df = df[df['frame'] <= end_frame]
    
    if format == "csv":
        return {"csv_data": df.to_csv()}
    else:
        return {
            "analog_info": {
                "id": analog.id,
                "name": analog.name,
                "units": analog.units,
                "scale": analog.scale,
                "offset": analog.offset
            },
            "data": df.to_dict('records')
        }

@router.get("/trials/{trial_id}/forceplates/{forceplate_id}/data")
def get_forceplate_data(
    trial_id: int, 
    forceplate_id: int, 
    session: SessionDep,
    format: Literal["json", "csv"] = Query("json", description="Output format")
):
    """Get force plate data."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    forceplate = session.get(ForcePlate, forceplate_id)
    if not forceplate or forceplate.trial_id != trial_id:
        raise HTTPException(status_code=404, detail="Force plate not found in this trial")
    
    # Get force plate data using the cached property
    df = forceplate.to_pandas
    
    if df.empty:
        return {"message": "No data available for this force plate"}
    
    if format == "csv":
        return {"csv_data": df.to_csv()}
    else:
        return {
            "forceplate_info": {
                "id": forceplate.id,
                "name": forceplate.name,
                "unit_force": forceplate.unit_force,
                "unit_moment": forceplate.unit_moment,
                "unit_position": forceplate.unit_position
            },
            "data": df.to_dict('records')
        }

@router.get("/trials/{trial_id}/statistics")
def get_trial_statistics(trial_id: int, session: SessionDep):
    """Get basic statistics for all data in a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    statistics = {
        "trial_id": trial_id,
        "markers": {},
        "analogs": {},
        "forceplates": {}
    }
    
    # Calculate marker statistics
    for marker in trial.markers:
        df = marker.to_pandas
        if not df.empty:
            statistics["markers"][marker.name] = {
                "count": len(df),
                "x": {"mean": df['x'].mean(), "std": df['x'].std(), "min": df['x'].min(), "max": df['x'].max()},
                "y": {"mean": df['y'].mean(), "std": df['y'].std(), "min": df['y'].min(), "max": df['y'].max()},
                "z": {"mean": df['z'].mean(), "std": df['z'].std(), "min": df['z'].min(), "max": df['z'].max()},
                "residual": {"mean": df['residual'].mean(), "std": df['residual'].std(), "min": df['residual'].min(), "max": df['residual'].max()}
            }
    
    # Calculate analog statistics
    for analog in trial.analogs:
        df = analog.to_pandas
        if not df.empty:
            statistics["analogs"][analog.name] = {
                "count": len(df),
                "value": {"mean": df['value'].mean(), "std": df['value'].std(), "min": df['value'].min(), "max": df['value'].max()}
            }
    
    # Calculate force plate statistics
    for forceplate in trial.forceplates:
        df = forceplate.to_pandas
        if not df.empty:
            statistics["forceplates"][forceplate.name] = {
                "count": len(df),
                "force": {
                    "x": {"mean": df['force_x'].mean(), "std": df['force_x'].std()},
                    "y": {"mean": df['force_y'].mean(), "std": df['force_y'].std()},
                    "z": {"mean": df['force_z'].mean(), "std": df['force_z'].std()}
                },
                "moment": {
                    "x": {"mean": df['moment_x'].mean(), "std": df['moment_x'].std()},
                    "y": {"mean": df['moment_y'].mean(), "std": df['moment_y'].std()},
                    "z": {"mean": df['moment_z'].mean(), "std": df['moment_z'].std()}
                },
                "cop": {
                    "x": {"mean": df['cop_x'].mean(), "std": df['cop_x'].std()},
                    "y": {"mean": df['cop_y'].mean(), "std": df['cop_y'].std()},
                    "z": {"mean": df['cop_z'].mean(), "std": df['cop_z'].std()}
                }
            }
    
    return statistics

@router.post("/trials/{trial_id}/export")
def export_trial_data(
    trial_id: int,
    session: SessionDep,
    format: Literal["csv", "json"] = "csv",
    include_markers: bool = True,
    include_analogs: bool = True,
    include_forceplates: bool = True
):
    """Export complete trial data in specified format."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    export_data = {
        "trial_info": {
            "id": trial.id,
            "name": trial.name,
            "description": trial.description,
            "rate": trial.rate
        }
    }
    
    if include_markers:
        export_data["markers"] = {}
        for marker in trial.markers:
            df = marker.to_pandas
            if not df.empty:
                if format == "csv":
                    export_data["markers"][marker.name] = df.to_csv()
                else:
                    export_data["markers"][marker.name] = df.to_dict('records')
    
    if include_analogs:
        export_data["analogs"] = {}
        for analog in trial.analogs:
            df = analog.to_pandas
            if not df.empty:
                if format == "csv":
                    export_data["analogs"][analog.name] = df.to_csv()
                else:
                    export_data["analogs"][analog.name] = df.to_dict('records')
    
    if include_forceplates:
        export_data["forceplates"] = {}
        for forceplate in trial.forceplates:
            df = forceplate.to_pandas
            if not df.empty:
                if format == "csv":
                    export_data["forceplates"][forceplate.name] = df.to_csv()
                else:
                    export_data["forceplates"][forceplate.name] = df.to_dict('records')
    
    return export_data


# =================== PLOTTING ENDPOINTS ===================

@router.get("/plots/marker-trajectory-3d/{trial_id}")
async def get_marker_trajectory_3d(
    trial_id: int,
    session: SessionDep,
    marker_names: Optional[List[str]] = Query(None, description="Specific marker names to plot"),
    start_time: Optional[float] = Query(None, description="Start time in seconds"),
    end_time: Optional[float] = Query(None, description="End time in seconds")
) -> Dict[str, Any]:
    """Get 3D marker trajectory plot configuration for frontend visualization."""
    plot_service = BiomechanicalPlotService(session)
    return plot_service.get_marker_trajectory_3d(trial_id, marker_names, start_time, end_time)

@router.get("/plots/config")
async def get_plot_config(session: SessionDep) -> Dict[str, Any]:
    """Get standard plot configuration for frontend applications."""
    plot_service = BiomechanicalPlotService(session)
    return plot_service.get_custom_plot_config()


@router.get("/plots/force-plate-timeseries/{trial_id}")
async def get_force_plate_timeseries(
    trial_id: int,
    session: SessionDep,
    force_plate_ids: Optional[List[int]] = Query(None, description="Specific force plate IDs"),
    components: List[str] = Query(['force_x', 'force_y', 'force_z'], description="Force components to plot"),
    normalize_time: bool = Query(True, description="Normalize time to percentage")
) -> Dict[str, Any]:
    """Get force plate time series plot configuration."""
    plot_service = BiomechanicalPlotService(session)
    return plot_service.get_force_plate_timeseries(trial_id, force_plate_ids, components, normalize_time)


@router.get("/plots/analog-signals/{trial_id}")
async def get_analog_signals(
    trial_id: int,
    session: SessionDep,
    analog_names: Optional[List[str]] = Query(None, description="Specific analog channel names"),
    start_time: Optional[float] = Query(None, description="Start time in seconds"),
    end_time: Optional[float] = Query(None, description="End time in seconds"),
    normalize_time: bool = Query(True, description="Normalize time to percentage")
) -> Dict[str, Any]:
    """Get analog signals plot configuration."""
    plot_service = BiomechanicalPlotService(session)
    return plot_service.get_analog_signals(trial_id, analog_names, start_time, end_time, normalize_time)


@router.get("/plots/gait-analysis/{trial_id}")
async def get_gait_analysis(
    trial_id: int,
    session: SessionDep,
    marker_name: str = Query("HEEL", description="Marker for gait analysis"),
    axis: str = Query("z", description="Axis for analysis (x, y, z)"),
    detect_events: bool = Query(True, description="Detect gait events")
) -> Dict[str, Any]:
    """Get gait analysis plot configuration."""
    plot_service = BiomechanicalPlotService(session)
    return plot_service.get_gait_analysis(trial_id, marker_name, axis, detect_events)


@router.get("/plots/trial-dashboard/{trial_id}")
async def get_trial_dashboard(
    trial_id: int,
    session: SessionDep
) -> Dict[str, Any]:
    """Get trial dashboard plot configuration."""
    plot_service = BiomechanicalPlotService(session)
    return plot_service.get_trial_dashboard(trial_id)


@router.get("/plots/3d-trial-visualizer/{trial_id}")
async def get_3d_trial_visualizer(
    trial_id: int,
    session: SessionDep,
    current_time: float = Query(0.0, description="Current time point in seconds"),
    time_window: float = Query(0.1, description="Time window around current time"),
    show_force_plates: bool = Query(True, description="Show force plate outlines"),
    show_force_vectors: bool = Query(True, description="Show force vectors as arrows"),
    show_markers: bool = Query(True, description="Show markers as spheres"),
    show_trajectories: bool = Query(True, description="Show marker trajectory trails"),
    trajectory_length: float = Query(1.0, description="Length of trajectory trails in seconds"),
    force_scale: float = Query(0.001, description="Scale factor for force vectors"),
    marker_size: int = Query(8, description="Size of marker spheres")
) -> Dict[str, Any]:
    """Get 3D trial visualizer configuration (Vicon Nexus style)."""
    plot_service = BiomechanicalPlotService(session)
    return plot_service.get_3d_trial_visualizer(
        trial_id=trial_id,
        current_time=current_time,
        time_window=time_window,
        show_force_plates=show_force_plates,
        show_force_vectors=show_force_vectors,
        show_markers=show_markers,
        show_trajectories=show_trajectories,
        trajectory_length=trajectory_length,
        force_scale=force_scale,
        marker_size=marker_size
    )


@router.get("/plots/trial-time-range/{trial_id}")
async def get_trial_time_range(
    trial_id: int,
    session: SessionDep
) -> Dict[str, Any]:
    """Get time range for a trial."""
    plot_service = BiomechanicalPlotService(session)
    return plot_service.get_trial_time_range(trial_id)
