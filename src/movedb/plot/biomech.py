"""
Biomechanical visualization module for MoveDB.

This module provides plotting functions that can be used directly in Jupyter notebooks
or called by the API service for frontend visualization.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
from plotly.subplots import make_subplots
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import timedelta
from sqlmodel import Session, select, col, col
from scipy.signal import find_peaks
import logging

from ..models.markers import Marker, MarkerData
from ..models.analogs import Analog, AnalogData
from ..models.forceplates import ForcePlate, ForcePlateData
from ..models.trial import Trial
from .trial_visualizer import create_3d_trial_visualizer, get_trial_time_bounds

logger = logging.getLogger(__name__)

# Define consistent color palette for biomechanical data
BIOMECH_COLORS = {
    'markers': px.colors.qualitative.Set1,
    'forces': px.colors.qualitative.Dark2,
    'analogs': px.colors.qualitative.Pastel1,
    'primary': '#1f77b4',
    'secondary': '#ff7f0e',
    'success': '#2ca02c',
    'danger': '#d62728',
    'warning': '#ff7f0e',
    'info': '#17a2b8'
}

# Standard plot configuration for consistent frontend rendering
PLOT_CONFIG = {
    "responsive": True,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
        "toggleSpikelines"
    ],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "biomech_plot",
        "height": 600,
        "width": 800,
        "scale": 2
    }
}

LAYOUT_DEFAULTS = {
    "font": {"family": "Arial, sans-serif", "size": 12},
    "plot_bgcolor": "white",
    "paper_bgcolor": "white",
    "margin": {"l": 50, "r": 50, "t": 80, "b": 50}
}


def plot_marker_trajectory_3d(
    session: Session,
    trial_id: int, 
    marker_names: Optional[List[str]] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    show_start_end: bool = True,
    return_json: bool = False
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Plot 3D marker trajectories with proper biomechanical visualization.
    
    Args:
        session: SQLModel database session
        trial_id: Trial ID to plot
        marker_names: Optional list of specific marker names to plot
        start_time: Start time in seconds (optional)
        end_time: End time in seconds (optional)
        show_start_end: Whether to show start/end markers
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        # Query markers for the trial
        markers_query = select(Marker).where(Marker.trial_id == trial_id)
        if marker_names:
            markers_query = markers_query.where(col(Marker.name).in_(marker_names))
        
        markers = session.exec(markers_query).all()
        
        if not markers:
            error_msg = "No markers found for the specified criteria"
            if return_json:
                return {"error": error_msg}
            else:
                print(f"Warning: {error_msg}")
                return go.Figure()
        
        fig = go.Figure()
        
        for i, marker in enumerate(markers):
            # Get marker data
            data_query = select(MarkerData).where(MarkerData.parent_id == marker.id)
            if start_time is not None:
                data_query = data_query.where(MarkerData.timestamp >= timedelta(seconds=start_time))
            if end_time is not None:
                data_query = data_query.where(MarkerData.timestamp <= timedelta(seconds=end_time))
            
            data = session.exec(data_query.order_by(MarkerData.timestamp)).all()
            
            if data:
                x_coords = [d.x for d in data]
                y_coords = [d.y for d in data]
                z_coords = [d.z for d in data]
                
                # Main trajectory
                color = BIOMECH_COLORS['markers'][i % len(BIOMECH_COLORS['markers'])]
                
                fig.add_trace(go.Scatter3d(
                    x=x_coords,
                    y=y_coords,
                    z=z_coords,
                    mode='lines+markers',
                    name=marker.name,
                    line=dict(width=4, color=color),
                    marker=dict(size=3, color=color),
                    hovertemplate=(
                        f"<b>{marker.name}</b><br>"
                        "X: %{x:.3f} m<br>"
                        "Y: %{y:.3f} m<br>"
                        "Z: %{z:.3f} m<br>"
                        "<extra></extra>"
                    )
                ))
                
                # Add start and end markers
                if show_start_end and len(x_coords) > 0:
                    # Start point
                    fig.add_trace(go.Scatter3d(
                        x=[x_coords[0]],
                        y=[y_coords[0]],
                        z=[z_coords[0]],
                        mode='markers',
                        name=f"{marker.name} Start",
                        marker=dict(size=8, color='green', symbol='diamond'),
                        showlegend=False,
                        hovertemplate=f"<b>{marker.name} Start</b><extra></extra>"
                    ))
                    
                    # End point
                    fig.add_trace(go.Scatter3d(
                        x=[x_coords[-1]],
                        y=[y_coords[-1]],
                        z=[z_coords[-1]],
                        mode='markers',
                        name=f"{marker.name} End",
                        marker=dict(size=8, color='red', symbol='x'),
                        showlegend=False,
                        hovertemplate=f"<b>{marker.name} End</b><extra></extra>"
                    ))
        
        # Calculate bounds for equal aspect ratio
        all_x, all_y, all_z = [], [], []
        for trace in fig.data:
            if hasattr(trace, 'x') and trace.x:
                all_x.extend(trace.x)
                all_y.extend(trace.y)
                all_z.extend(trace.z)
        
        if all_x:
            x_range = [min(all_x), max(all_x)]
            y_range = [min(all_y), max(all_y)]
            z_range = [min(all_z), max(all_z)]
            
            # Make ranges equal for proper aspect ratio
            max_range = max(
                x_range[1] - x_range[0],
                y_range[1] - y_range[0],
                z_range[1] - z_range[0]
            )
            
            center_x = (x_range[0] + x_range[1]) / 2
            center_y = (y_range[0] + y_range[1]) / 2
            center_z = (z_range[0] + z_range[1]) / 2
            
            scene_range = max_range / 2 * 1.1  # Add 10% padding
        else:
            center_x = center_y = center_z = 0
            scene_range = 1
        
        fig.update_layout(
            title={
                'text': f"3D Marker Trajectories - Trial {trial_id}",
                'x': 0.5,
                'xanchor': 'center'
            },
            scene=dict(
                xaxis=dict(
                    title="X (m)",
                    range=[center_x - scene_range, center_x + scene_range]
                ),
                yaxis=dict(
                    title="Y (m)", 
                    range=[center_y - scene_range, center_y + scene_range]
                ),
                zaxis=dict(
                    title="Z (m)",
                    range=[center_z - scene_range, center_z + scene_range]
                ),
                aspectmode='cube',
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.5)
                )
            ),
            showlegend=True,
            height=600,
            margin=dict(l=0, r=0, t=50, b=0),
            **LAYOUT_DEFAULTS
        )
        
        if return_json:
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
        else:
            return fig
            
    except Exception as e:
        logger.error(f"Error generating 3D marker trajectory plot: {e}")
        error_msg = str(e)
        if return_json:
            return {"error": error_msg}
        else:
            print(f"Error: {error_msg}")
            return go.Figure()


def plot_force_plate_timeseries(
    session: Session,
    trial_id: int,
    force_plate_ids: Optional[List[int]] = None,
    components: List[str] = ['force_x', 'force_y', 'force_z'],
    normalize_time: bool = True,
    return_json: bool = False
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Plot force plate time series data.
    
    Args:
        session: SQLModel database session
        trial_id: Trial ID to plot
        force_plate_ids: Optional list of specific force plate IDs
        components: List of components to plot
        normalize_time: Whether to normalize time to start from 0
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        # Query force plates
        fp_query = select(ForcePlate).where(ForcePlate.trial_id == trial_id)
        if force_plate_ids:
            fp_query = fp_query.where(col(ForcePlate.id).in_(force_plate_ids))
        
        force_plates = session.exec(fp_query).all()
        
        if not force_plates:
            error_msg = "No force plates found for the specified criteria"
            if return_json:
                return {"error": error_msg}
            else:
                print(f"Warning: {error_msg}")
                return go.Figure()
        
        fig = go.Figure()
        
        valid_components = ['force_x', 'force_y', 'force_z', 'moment_x', 'moment_y', 'moment_z']
        components = [c for c in components if c in valid_components]
        
        if not components:
            error_msg = f"No valid components specified. Valid options: {valid_components}"
            if return_json:
                return {"error": error_msg}
            else:
                print(f"Warning: {error_msg}")
                return go.Figure()
        
        colors = BIOMECH_COLORS['forces']
        
        for i, fp in enumerate(force_plates):
            # Get force plate data
            data = session.exec(
                select(ForcePlateData)
                .where(ForcePlateData.parent_id == fp.id)
                .order_by(ForcePlateData.timestamp)
            ).all()
            
            if data:
                timestamps = [d.timestamp.total_seconds() for d in data]
                
                # Normalize time to start from 0 if requested
                if normalize_time and timestamps:
                    start_time = timestamps[0]
                    timestamps = [t - start_time for t in timestamps]
                
                for j, comp in enumerate(components):
                    if hasattr(data[0], comp):
                        values = [getattr(d, comp) for d in data]
                        
                        # Determine units and color
                        if 'force' in comp:
                            units = 'N'
                            y_title = 'Force (N)'
                        elif 'moment' in comp:
                            units = 'N⋅m'
                            y_title = 'Moment (N⋅m)'
                        else:
                            units = ''
                            y_title = 'Value'
                        
                        # Create trace name
                        trace_name = f"FP{fp.id} {comp.replace('_', ' ').title()}"
                        
                        color = colors[(i * len(components) + j) % len(colors)]
                        
                        fig.add_trace(go.Scatter(
                            x=timestamps,
                            y=values,
                            mode='lines',
                            name=trace_name,
                            line=dict(color=color, width=2),
                            hovertemplate=(
                                f"<b>{trace_name}</b><br>"
                                "Time: %{x:.3f} s<br>"
                                f"Value: %{{y:.2f}} {units}<br>"
                                "<extra></extra>"
                            )
                        ))
        
        # Determine y-axis title based on components
        if all('force' in comp for comp in components):
            y_title = 'Force (N)'
        elif all('moment' in comp for comp in components):
            y_title = 'Moment (N⋅m)'
        else:
            y_title = 'Value'
        
        fig.update_layout(
            title={
                'text': f"Force Plate Data - Trial {trial_id}",
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis_title="Time (s)",
            yaxis_title=y_title,
            showlegend=True,
            height=500,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            **LAYOUT_DEFAULTS
        )
        
        if return_json:
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
        else:
            return fig
            
    except Exception as e:
        logger.error(f"Error generating force plate time series plot: {e}")
        error_msg = str(e)
        if return_json:
            return {"error": error_msg}
        else:
            print(f"Error: {error_msg}")
            return go.Figure()


def plot_analog_signals(
    session: Session,
    trial_id: int,
    analog_names: Optional[List[str]] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    normalize_time: bool = True,
    return_json: bool = False
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Plot analog signal time series.
    
    Args:
        session: SQLModel database session
        trial_id: Trial ID to plot
        analog_names: Optional list of specific analog channel names
        start_time: Start time in seconds (optional)
        end_time: End time in seconds (optional)
        normalize_time: Whether to normalize time to start from 0
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        # Query analog channels
        analog_query = select(Analog).where(Analog.trial_id == trial_id)
        if analog_names:
            analog_query = analog_query.where(col(Analog.name).in_(analog_names))
        
        analogs = session.exec(analog_query).all()
        
        if not analogs:
            error_msg = "No analog channels found for the specified criteria"
            if return_json:
                return {"error": error_msg}
            else:
                print(f"Warning: {error_msg}")
                return go.Figure()
        
        fig = go.Figure()
        colors = BIOMECH_COLORS['analogs']
        
        for i, analog in enumerate(analogs):
            # Get analog data
            data_query = select(AnalogData).where(AnalogData.parent_id == analog.id)
            if start_time is not None:
                data_query = data_query.where(AnalogData.timestamp >= timedelta(seconds=start_time))
            if end_time is not None:
                data_query = data_query.where(AnalogData.timestamp <= timedelta(seconds=end_time))
            
            data = session.exec(data_query.order_by(AnalogData.timestamp)).all()
            
            if data:
                timestamps = [d.timestamp.total_seconds() for d in data]
                
                # Normalize time to start from 0 if requested
                if normalize_time and timestamps:
                    start_time_actual = timestamps[0]
                    timestamps = [t - start_time_actual for t in timestamps]
                
                # Apply scale and offset
                values = [d.value * analog.scale + analog.offset for d in data]
                
                color = colors[i % len(colors)]
                
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=values,
                    mode='lines',
                    name=f"{analog.name} ({analog.units})" if analog.units else analog.name,
                    line=dict(color=color, width=2),
                    hovertemplate=(
                        f"<b>{analog.name}</b><br>"
                        "Time: %{x:.3f} s<br>"
                        f"Value: %{{y:.3f}} {analog.units or ''}<br>"
                        "<extra></extra>"
                    )
                ))
        
        fig.update_layout(
            title={
                'text': f"Analog Signals - Trial {trial_id}",
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis_title="Time (s)",
            yaxis_title="Signal Value",
            showlegend=True,
            height=400,
            hovermode='x unified',
            **LAYOUT_DEFAULTS
        )
        
        if return_json:
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
        else:
            return fig
            
    except Exception as e:
        logger.error(f"Error generating analog signals plot: {e}")
        error_msg = str(e)
        if return_json:
            return {"error": error_msg}
        else:
            print(f"Error: {error_msg}")
            return go.Figure()


def plot_gait_analysis(
    session: Session,
    trial_id: int,
    marker_name: str = "HEEL",
    axis: str = "z",
    detect_events: bool = True,
    return_json: bool = False
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Plot gait cycle analysis with event detection.
    
    Args:
        session: SQLModel database session
        trial_id: Trial ID to analyze
        marker_name: Name of the marker to analyze
        axis: Axis to analyze ('x', 'y', or 'z')
        detect_events: Whether to detect and mark gait events
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        marker = session.exec(
            select(Marker).where(
                Marker.trial_id == trial_id,
                Marker.name == marker_name
            )
        ).first()
        
        if not marker:
            error_msg = f"Marker {marker_name} not found in trial {trial_id}"
            if return_json:
                return {"error": error_msg}
            else:
                print(f"Warning: {error_msg}")
                return go.Figure()
        
        data = session.exec(
            select(MarkerData)
            .where(MarkerData.parent_id == marker.id)
            .order_by(MarkerData.timestamp)
        ).all()
        
        if not data:
            error_msg = f"No data found for marker {marker_name}"
            if return_json:
                return {"error": error_msg}
            else:
                print(f"Warning: {error_msg}")
                return go.Figure()
        
        timestamps = [d.timestamp.total_seconds() for d in data]
        start_time = timestamps[0]
        timestamps = [t - start_time for t in timestamps]  # Normalize to start from 0
        
        if axis not in ['x', 'y', 'z']:
            error_msg = f"Invalid axis '{axis}'. Must be 'x', 'y', or 'z'"
            if return_json:
                return {"error": error_msg}
            else:
                print(f"Error: {error_msg}")
                return go.Figure()
        
        values = [getattr(d, axis) for d in data]
        
        fig = go.Figure()
        
        # Main trajectory
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=values,
            mode='lines',
            name=f"{marker_name} {axis.upper()}",
            line=dict(color=BIOMECH_COLORS['primary'], width=3),
            hovertemplate=(
                f"<b>{marker_name} {axis.upper()}</b><br>"
                "Time: %{x:.3f} s<br>"
                "Position: %{y:.3f} m<br>"
                "<extra></extra>"
            )
        ))
        
        # Event detection for gait analysis
        if detect_events and len(values) > 10:
            try:
                # Simple heel strike detection (local minima for vertical position)
                if axis == 'z':
                    # For heel strikes, look for local minima
                    peaks, _ = find_peaks(-np.array(values), height=None, distance=int(len(values)*0.1))
                else:
                    # For other axes, look for peaks
                    peaks, _ = find_peaks(np.array(values), height=None, distance=int(len(values)*0.1))
                
                if len(peaks) > 0:
                    peak_times = [timestamps[i] for i in peaks]
                    peak_values = [values[i] for i in peaks]
                    
                    event_name = "Heel Strikes" if axis == 'z' else f"{axis.upper()} Peaks"
                    
                    fig.add_trace(go.Scatter(
                        x=peak_times,
                        y=peak_values,
                        mode='markers',
                        name=event_name,
                        marker=dict(
                            color='red',
                            size=10,
                            symbol='diamond',
                            line=dict(color='darkred', width=2)
                        ),
                        hovertemplate=(
                            f"<b>{event_name}</b><br>"
                            "Time: %{x:.3f} s<br>"
                            "Position: %{y:.3f} m<br>"
                            "<extra></extra>"
                        )
                    ))
                    
                    # Add vertical lines for events
                    for peak_time in peak_times:
                        fig.add_vline(
                            x=peak_time,
                            line_dash="dash",
                            line_color="red",
                            opacity=0.5,
                            annotation_text=f"Event at {peak_time:.2f}s",
                            annotation_position="top"
                        )
            
            except Exception as e:
                logger.warning(f"Event detection failed: {e}")
                if not return_json:
                    print(f"Warning: Event detection failed: {e}")
        
        fig.update_layout(
            title={
                'text': f"Gait Analysis - {marker_name} {axis.upper()} - Trial {trial_id}",
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis_title="Time (s)",
            yaxis_title=f"Position {axis.upper()} (m)",
            showlegend=True,
            height=500,
            hovermode='x unified',
            **LAYOUT_DEFAULTS
        )
        
        if return_json:
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
        else:
            return fig
            
    except Exception as e:
        logger.error(f"Error generating gait cycle analysis: {e}")
        error_msg = str(e)
        if return_json:
            return {"error": error_msg}
        else:
            print(f"Error: {error_msg}")
            return go.Figure()


def plot_trial_dashboard(
    session: Session,
    trial_id: int,
    return_json: bool = False
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Generate a comprehensive dashboard overview of trial data.
    
    Args:
        session: SQLModel database session
        trial_id: Trial ID to analyze
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        trial = session.get(Trial, trial_id)
        if not trial:
            error_msg = f"Trial {trial_id} not found"
            if return_json:
                return {"error": error_msg}
            else:
                print(f"Error: {error_msg}")
                return go.Figure()
        
        # Get data counts
        markers = session.exec(select(Marker).where(Marker.trial_id == trial_id)).all()
        force_plates = session.exec(select(ForcePlate).where(ForcePlate.trial_id == trial_id)).all()
        analogs = session.exec(select(Analog).where(Analog.trial_id == trial_id)).all()
        
        # Create subplot figure
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Data Overview", 
                "Marker Distribution", 
                "Force Plate Summary",
                "Trial Information"
            ),
            specs=[
                [{"type": "bar"}, {"type": "scatter"}],
                [{"type": "bar"}, {"type": "table"}]
            ]
        )
        
        # 1. Data overview bar chart
        data_types = ["Markers", "Force Plates", "Analog Channels"]
        data_counts = [len(markers), len(force_plates), len(analogs)]
        
        fig.add_trace(
            go.Bar(
                x=data_types,
                y=data_counts,
                name="Data Count",
                marker=dict(color=[BIOMECH_COLORS['primary'], BIOMECH_COLORS['secondary'], BIOMECH_COLORS['success']]),
                text=data_counts,
                textposition='auto',
            ),
            row=1, col=1
        )
        
        # 2. Marker distribution (if markers exist)
        if markers:
            marker_names = [m.name for m in markers[:10]]  # Limit to first 10 for readability
            marker_data_counts = []
            
            for marker in markers[:10]:
                count = len(session.exec(
                    select(MarkerData).where(MarkerData.parent_id == marker.id)
                ).all())
                marker_data_counts.append(count)
            
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(marker_names))),
                    y=marker_data_counts,
                    mode='markers+lines',
                    name="Data Points",
                    marker=dict(size=8, color=BIOMECH_COLORS['primary']),
                    text=marker_names,
                    hovertemplate="<b>%{text}</b><br>Data Points: %{y}<extra></extra>"
                ),
                row=1, col=2
            )
        
        # 3. Force plate summary
        if force_plates:
            fp_names = [f"FP {fp.id}" for fp in force_plates]
            fp_data_counts = []
            
            for fp in force_plates:
                count = len(session.exec(
                    select(ForcePlateData).where(ForcePlateData.parent_id == fp.id)
                ).all())
                fp_data_counts.append(count)
            
            fig.add_trace(
                go.Bar(
                    x=fp_names,
                    y=fp_data_counts,
                    name="FP Data Points",
                    marker=dict(color=BIOMECH_COLORS['secondary']),
                    text=fp_data_counts,
                    textposition='auto',
                ),
                row=2, col=1
            )
        
        # 4. Trial information table
        info_data = [
            ["Trial ID", str(trial_id)],
            ["Name", trial.name or "Unnamed"],
            ["Description", getattr(trial, 'description', 'No description') or "No description"],
            ["Markers", str(len(markers))],
            ["Force Plates", str(len(force_plates))],
            ["Analog Channels", str(len(analogs))],
        ]
        
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Property", "Value"],
                    fill_color=BIOMECH_COLORS['primary'],
                    font=dict(color='white', size=12),
                    align="left"
                ),
                cells=dict(
                    values=list(zip(*info_data)),
                    fill_color='lightgray',
                    align="left",
                    font=dict(size=11)
                )
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title={
                'text': f"Trial {trial_id} Overview Dashboard",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20}
            },
            height=800,
            showlegend=False,
            margin=dict(t=100),
            **LAYOUT_DEFAULTS
        )
        
        # Update subplot titles
        fig.update_xaxes(title_text="Data Type", row=1, col=1)
        fig.update_yaxes(title_text="Count", row=1, col=1)
        
        if markers:
            fig.update_xaxes(title_text="Marker Index", row=1, col=2)
            fig.update_yaxes(title_text="Data Points", row=1, col=2)
        
        if force_plates:
            fig.update_xaxes(title_text="Force Plate", row=2, col=1)
            fig.update_yaxes(title_text="Data Points", row=2, col=1)
        
        if return_json:
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
        else:
            return fig
            
    except Exception as e:
        logger.error(f"Error generating trial overview dashboard: {e}")
        error_msg = str(e)
        if return_json:
            return {"error": error_msg}
        else:
            print(f"Error: {error_msg}")
            return go.Figure()


def get_plot_config() -> Dict[str, Any]:
    """Get the standard plot configuration for frontend applications."""
    return {
        "config": PLOT_CONFIG,
        "layout_defaults": LAYOUT_DEFAULTS,
        "colors": BIOMECH_COLORS
    }


def plot_3d_trial_visualizer(
    session: Session,
    trial_id: int,
    current_time: float = 0.0,
    time_window: float = 0.1,
    show_force_plates: bool = True,
    show_force_vectors: bool = True,
    show_markers: bool = True,
    show_trajectories: bool = True,
    trajectory_length: float = 1.0,
    force_scale: float = 0.001,
    marker_size: int = 8,
    return_json: bool = False
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Create a comprehensive 3D trial visualizer similar to Vicon Nexus.
    
    Args:
        session: SQLModel database session
        trial_id: Trial ID to visualize
        current_time: Current time point to display (seconds)
        time_window: Time window around current_time to show data (seconds)
        show_force_plates: Whether to show force plate outlines
        show_force_vectors: Whether to show force vectors as arrows
        show_markers: Whether to show markers as spheres
        show_trajectories: Whether to show marker trajectory trails
        trajectory_length: Length of trajectory trails in seconds
        force_scale: Scale factor for force vector arrows
        marker_size: Size of marker spheres
        return_json: If True, return JSON for API; if False, return Figure
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    return create_3d_trial_visualizer(
        session=session,
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
        return_json=return_json
    )


def get_trial_time_range(session: Session, trial_id: int) -> Dict[str, float]:
    """
    Get the time range for a trial.
    
    Args:
        session: SQLModel database session
        trial_id: Trial ID to query
        
    Returns:
        Dictionary with min_time and max_time in seconds
    """
    min_time, max_time = get_trial_time_bounds(session, trial_id)
    return {
        "min_time": min_time,
        "max_time": max_time,
        "duration": max_time - min_time
    }
