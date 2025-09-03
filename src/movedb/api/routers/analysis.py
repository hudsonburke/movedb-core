from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from typing import Any, Optional, Literal
import pandas as pd
import numpy as np
from ..dependencies import SessionDep
from ...models import Trial, Marker, Analog, ForcePlate

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
