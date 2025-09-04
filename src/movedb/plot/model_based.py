"""
Biomechanical visualization module for MoveDB - Model-based plotting.

This module provides plotting functions that work directly with movedb Trial objects
and leverage the optimized to_polars dataframe conversion methods.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
from plotly.subplots import make_subplots
import json
import numpy as np
import polars as pl
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import timedelta
import logging

# Import movedb models
from ..models.trial import Trial
from ..models.markers import Marker
from ..models.analogs import Analog
from ..models.forceplates import ForcePlate

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


def _timedelta_to_seconds(df: pl.DataFrame, time_col: str = "timestamp") -> pl.DataFrame:
    """Convert timedelta column to seconds for plotly compatibility."""
    return df.with_columns(
        pl.col(time_col).dt.total_seconds().alias("time_seconds")
    )


def _filter_by_time_range(df: pl.DataFrame, 
                         start_time: Optional[float] = None, 
                         end_time: Optional[float] = None,
                         time_col: str = "time_seconds") -> pl.DataFrame:
    """Filter dataframe by time range in seconds."""
    if start_time is not None:
        df = df.filter(pl.col(time_col) >= start_time)
    if end_time is not None:
        df = df.filter(pl.col(time_col) <= end_time)
    return df


def plot_marker_trajectory_3d(
    trial: Trial,
    marker_names: Optional[List[str]] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    show_start_end: bool = True,
    return_json: bool = False,
    title: Optional[str] = None
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Plot 3D marker trajectories using Trial model data.
    
    Args:
        trial: Trial object containing marker data
        marker_names: Optional list of specific marker names to plot
        start_time: Start time in seconds (optional)
        end_time: End time in seconds (optional)
        show_start_end: Whether to show start/end markers
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        title: Plot title (auto-generated if None)
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        # Get marker dataframe using the trial's optimized method
        markers_df = trial.markers_to_dataframe()
        
        if markers_df.is_empty():
            raise ValueError("No marker data found in trial")
        
        # Convert timestamps to seconds for plotly
        markers_df = _timedelta_to_seconds(markers_df)
        
        # Filter by marker names if specified
        if marker_names:
            markers_df = markers_df.filter(pl.col("marker_name").is_in(marker_names))
            
        if markers_df.is_empty():
            raise ValueError("No markers found matching the specified names")
        
        # Filter by time range if specified
        markers_df = _filter_by_time_range(markers_df, start_time, end_time)
        
        if markers_df.is_empty():
            raise ValueError("No data found in specified time range")
        
        fig = go.Figure()
        
        # Get unique marker names for iteration
        unique_markers = markers_df["marker_name"].unique().to_list()
        
        for i, marker_name in enumerate(unique_markers):
            marker_data = markers_df.filter(pl.col("marker_name") == marker_name)
            
            if marker_data.is_empty():
                continue
            
            # Extract coordinates
            x_coords = marker_data["x"].to_numpy()
            y_coords = marker_data["y"].to_numpy()
            z_coords = marker_data["z"].to_numpy()
            
            # Color cycling
            color = BIOMECH_COLORS['markers'][i % len(BIOMECH_COLORS['markers'])]
            
            # Add trajectory line
            fig.add_trace(go.Scatter3d(
                x=x_coords,
                y=y_coords,
                z=z_coords,
                mode='lines',
                name=f'{marker_name} trajectory',
                line=dict(color=color, width=3),
                hovertemplate=(
                    f"<b>{marker_name}</b><br>"
                    "X: %{x:.2f} mm<br>"
                    "Y: %{y:.2f} mm<br>"
                    "Z: %{z:.2f} mm<br>"
                    "<extra></extra>"
                )
            ))
            
            if show_start_end and len(x_coords) > 0:
                # Add start marker
                fig.add_trace(go.Scatter3d(
                    x=[x_coords[0]],
                    y=[y_coords[0]],
                    z=[z_coords[0]],
                    mode='markers',
                    name=f'{marker_name} start',
                    marker=dict(
                        color='green',
                        size=8,
                        symbol='circle'
                    ),
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{marker_name} START</b><br>"
                        "X: %{x:.2f} mm<br>"
                        "Y: %{y:.2f} mm<br>"
                        "Z: %{z:.2f} mm<br>"
                        "<extra></extra>"
                    )
                ))
                
                # Add end marker
                fig.add_trace(go.Scatter3d(
                    x=[x_coords[-1]],
                    y=[y_coords[-1]],
                    z=[z_coords[-1]],
                    mode='markers',
                    name=f'{marker_name} end',
                    marker=dict(
                        color='red',
                        size=8,
                        symbol='square'
                    ),
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{marker_name} END</b><br>"
                        "X: %{x:.2f} mm<br>"
                        "Y: %{y:.2f} mm<br>"
                        "Z: %{z:.2f} mm<br>"
                        "<extra></extra>"
                    )
                ))
        
        # Update layout for 3D scene
        plot_title = title or f"Trial {trial.name or trial.id} - 3D Marker Trajectories"
        
        fig.update_layout(
            title=plot_title,
            scene=dict(
                xaxis_title="X (mm)",
                yaxis_title="Y (mm)",
                zaxis_title="Z (mm)",
                aspectmode='cube',
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.5)
                )
            ),
            **LAYOUT_DEFAULTS
        )
        
        if return_json:
            return {
                "data": json.loads(json.dumps(fig.to_dict()["data"], cls=PlotlyJSONEncoder)),
                "layout": json.loads(json.dumps(fig.to_dict()["layout"], cls=PlotlyJSONEncoder)),
                "config": PLOT_CONFIG
            }
        
        return fig
        
    except Exception as e:
        logger.error(f"Error in plot_marker_trajectory_3d: {str(e)}")
        if return_json:
            return {"error": str(e)}
        raise


def plot_force_plate_timeseries(
    trial: Trial,
    plate_names: Optional[List[str]] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    show_moments: bool = True,
    return_json: bool = False,
    title: Optional[str] = None
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Plot force plate time series data using Trial model data.
    
    Args:
        trial: Trial object containing force plate data
        plate_names: Optional list of specific plate names to plot
        start_time: Start time in seconds (optional)
        end_time: End time in seconds (optional)
        show_moments: Whether to show moments subplot
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        title: Plot title (auto-generated if None)
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        # Get force plate dataframe using the trial's optimized method
        forceplates_df = trial.forceplates_to_dataframe()
        
        if forceplates_df.is_empty():
            raise ValueError("No force plate data found in trial")
        
        # Convert timestamps to seconds for plotly
        forceplates_df = _timedelta_to_seconds(forceplates_df)
        
        # Filter by plate names if specified
        if plate_names:
            forceplates_df = forceplates_df.filter(pl.col("forceplate_name").is_in(plate_names))
            
        if forceplates_df.is_empty():
            raise ValueError("No force plates found matching the specified names")
        
        # Filter by time range if specified
        forceplates_df = _filter_by_time_range(forceplates_df, start_time, end_time)
        
        if forceplates_df.is_empty():
            raise ValueError("No data found in specified time range")
        
        # Create subplots
        subplot_titles = ["Forces (N)"]
        if show_moments:
            subplot_titles.append("Moments (N⋅mm)")
        
        fig = make_subplots(
            rows=2 if show_moments else 1,
            cols=1,
            subplot_titles=subplot_titles,
            vertical_spacing=0.1
        )
        
        # Get unique plate names for iteration
        unique_plates = forceplates_df["forceplate_name"].unique().to_list()
        
        for plate_name in unique_plates:
            plate_data = forceplates_df.filter(pl.col("forceplate_name") == plate_name)
            
            if plate_data.is_empty():
                continue
            
            times = plate_data["time_seconds"].to_numpy()
            
            # Plot forces
            for axis, color in zip(['x', 'y', 'z'], ['red', 'green', 'blue']):
                force_values = plate_data[f"force_{axis}"].to_numpy()
                
                fig.add_trace(go.Scatter(
                    x=times,
                    y=force_values,
                    mode='lines',
                    name=f'{plate_name} F{axis.upper()}',
                    line=dict(color=color),
                    hovertemplate=(
                        f"<b>{plate_name} - F{axis.upper()}</b><br>"
                        "Time: %{x:.3f} s<br>"
                        "Force: %{y:.1f} N<br>"
                        "<extra></extra>"
                    )
                ), row=1, col=1)
            
            # Plot moments if requested
            if show_moments:
                for axis, color in zip(['x', 'y', 'z'], ['red', 'green', 'blue']):
                    moment_values = plate_data[f"moment_{axis}"].to_numpy()
                    
                    fig.add_trace(go.Scatter(
                        x=times,
                        y=moment_values,
                        mode='lines',
                        name=f'{plate_name} M{axis.upper()}',
                        line=dict(color=color, dash='dash'),
                        hovertemplate=(
                            f"<b>{plate_name} - M{axis.upper()}</b><br>"
                            "Time: %{x:.3f} s<br>"
                            "Moment: %{y:.1f} N⋅mm<br>"
                            "<extra></extra>"
                        ),
                        showlegend=False
                    ), row=2, col=1)
        
        # Update layout
        plot_title = title or f"Trial {trial.name or trial.id} - Force Plate Time Series"
        
        fig.update_xaxes(title_text="Time (s)")
        fig.update_yaxes(title_text="Force (N)", row=1, col=1)
        if show_moments:
            fig.update_yaxes(title_text="Moment (N⋅mm)", row=2, col=1)
        
        fig.update_layout(
            title=plot_title,
            height=600 if show_moments else 400,
            **LAYOUT_DEFAULTS
        )
        
        if return_json:
            return {
                "data": json.loads(json.dumps(fig.to_dict()["data"], cls=PlotlyJSONEncoder)),
                "layout": json.loads(json.dumps(fig.to_dict()["layout"], cls=PlotlyJSONEncoder)),
                "config": PLOT_CONFIG
            }
        
        return fig
        
    except Exception as e:
        logger.error(f"Error in plot_force_plate_timeseries: {str(e)}")
        if return_json:
            return {"error": str(e)}
        raise


def plot_analog_signals(
    trial: Trial,
    analog_names: Optional[List[str]] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    normalize: bool = False,
    return_json: bool = False,
    title: Optional[str] = None
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Plot analog signal time series data using Trial model data.
    
    Args:
        trial: Trial object containing analog data
        analog_names: Optional list of specific analog names to plot
        start_time: Start time in seconds (optional)
        end_time: End time in seconds (optional)
        normalize: Whether to normalize signals to [0,1]
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        title: Plot title (auto-generated if None)
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        # Get analog dataframe using the trial's optimized method
        analogs_df = trial.analogs_to_dataframe()
        
        if analogs_df.is_empty():
            raise ValueError("No analog data found in trial")
        
        # Convert timestamps to seconds for plotly
        analogs_df = _timedelta_to_seconds(analogs_df)
        
        # Filter by analog names if specified
        if analog_names:
            analogs_df = analogs_df.filter(pl.col("analog_name").is_in(analog_names))
            
        if analogs_df.is_empty():
            raise ValueError("No analogs found matching the specified names")
        
        # Filter by time range if specified
        analogs_df = _filter_by_time_range(analogs_df, start_time, end_time)
        
        if analogs_df.is_empty():
            raise ValueError("No data found in specified time range")
        
        # Normalize if requested
        if normalize:
            analogs_df = analogs_df.with_columns([
                ((pl.col("value") - pl.col("value").min().over("analog_name")) / 
                 (pl.col("value").max().over("analog_name") - pl.col("value").min().over("analog_name"))).alias("value")
            ])
        
        fig = go.Figure()
        
        # Get unique analog names for iteration
        unique_analogs = analogs_df["analog_name"].unique().to_list()
        
        for i, analog_name in enumerate(unique_analogs):
            analog_data = analogs_df.filter(pl.col("analog_name") == analog_name)
            
            if analog_data.is_empty():
                continue
            
            times = analog_data["time_seconds"].to_numpy()
            values = analog_data["value"].to_numpy()
            
            color = BIOMECH_COLORS['analogs'][i % len(BIOMECH_COLORS['analogs'])]
            
            fig.add_trace(go.Scatter(
                x=times,
                y=values,
                mode='lines',
                name=analog_name,
                line=dict(color=color),
                hovertemplate=(
                    f"<b>{analog_name}</b><br>"
                    "Time: %{x:.3f} s<br>"
                    "Value: %{y:.3f}<br>"
                    "<extra></extra>"
                )
            ))
        
        # Update layout
        plot_title = title or f"Trial {trial.name or trial.id} - Analog Signals"
        y_title = "Normalized Value" if normalize else "Value"
        
        fig.update_layout(
            title=plot_title,
            xaxis_title="Time (s)",
            yaxis_title=y_title,
            height=400,
            **LAYOUT_DEFAULTS
        )
        
        if return_json:
            return {
                "data": json.loads(json.dumps(fig.to_dict()["data"], cls=PlotlyJSONEncoder)),
                "layout": json.loads(json.dumps(fig.to_dict()["layout"], cls=PlotlyJSONEncoder)),
                "config": PLOT_CONFIG
            }
        
        return fig
        
    except Exception as e:
        logger.error(f"Error in plot_analog_signals: {str(e)}")
        if return_json:
            return {"error": str(e)}
        raise


def plot_trial_dashboard(
    trial: Trial,
    return_json: bool = False
) -> Union[Dict[str, go.Figure], Dict[str, Any]]:
    """
    Create a comprehensive dashboard for trial data using Trial model.
    
    Args:
        trial: Trial object containing all trial information
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        
    Returns:
        Dictionary of Plotly figures or JSON configurations
    """
    
    try:
        dashboard = {}
        
        # Create individual plots if data exists
        if trial.markers:
            dashboard['markers_3d'] = plot_marker_trajectory_3d(
                trial,
                return_json=return_json,
                title=f"Trial {trial.name or trial.id} - Marker Trajectories"
            )
        
        if trial.forceplates:
            dashboard['force_plates'] = plot_force_plate_timeseries(
                trial,
                return_json=return_json,
                title=f"Trial {trial.name or trial.id} - Force Plates"
            )
        
        if trial.analogs:
            dashboard['analogs'] = plot_analog_signals(
                trial,
                return_json=return_json,
                title=f"Trial {trial.name or trial.id} - Analog Signals"
            )
        
        return dashboard
        
    except Exception as e:
        logger.error(f"Error in plot_trial_dashboard: {str(e)}")
        if return_json:
            return {"error": str(e)}
        raise


def plot_gait_analysis(
    trial: Trial,
    gait_events: Optional[List[Dict[str, Any]]] = None,
    return_json: bool = False,
    title: Optional[str] = None
) -> Union[go.Figure, Dict[str, Any]]:
    """
    Create specialized gait analysis visualization using Trial model data.
    
    Args:
        trial: Trial object containing gait analysis data
        gait_events: Optional list of gait events (heel strike, toe off, etc.)
        return_json: If True, return JSON for API; if False, return Figure for Jupyter
        title: Plot title (auto-generated if None)
        
    Returns:
        Plotly Figure object for Jupyter or JSON dict for API
    """
    
    try:
        # Get dataframes using the trial's optimized methods
        markers_df = trial.markers_to_dataframe()
        forceplates_df = trial.forceplates_to_dataframe()
        
        if markers_df.is_empty() and forceplates_df.is_empty():
            raise ValueError("No gait analysis data found in trial")
        
        # Convert timestamps to seconds
        if not markers_df.is_empty():
            markers_df = _timedelta_to_seconds(markers_df)
        if not forceplates_df.is_empty():
            forceplates_df = _timedelta_to_seconds(forceplates_df)
        
        # Create subplots for different aspects of gait
        fig = make_subplots(
            rows=3,
            cols=1,
            subplot_titles=[
                "Ground Reaction Forces",
                "Marker Heights", 
                "Gait Pattern"
            ],
            vertical_spacing=0.1
        )
        
        # Plot ground reaction forces
        if not forceplates_df.is_empty():
            unique_plates = forceplates_df["forceplate_name"].unique().to_list()
            
            for plate_name in unique_plates:
                plate_data = forceplates_df.filter(pl.col("forceplate_name") == plate_name)
                times = plate_data["time_seconds"].to_numpy()
                vertical_forces = plate_data["force_z"].to_numpy()
                
                fig.add_trace(go.Scatter(
                    x=times,
                    y=vertical_forces,
                    mode='lines',
                    name=f'{plate_name} Vertical Force',
                    line=dict(width=2),
                    hovertemplate=(
                        f"<b>{plate_name}</b><br>"
                        "Time: %{x:.3f} s<br>"
                        "Vertical Force: %{y:.1f} N<br>"
                        "<extra></extra>"
                    )
                ), row=1, col=1)
        
        # Plot marker heights (heel and toe markers for gait analysis)
        if not markers_df.is_empty():
            # Filter for gait-relevant markers
            gait_keywords = ['heel', 'toe', 'cal', 'met', 'ankle']
            gait_markers = markers_df.filter(
                pl.col("marker_name").str.to_lowercase().str.contains("|".join(gait_keywords))
            )
            
            if not gait_markers.is_empty():
                unique_gait_markers = gait_markers["marker_name"].unique().to_list()
                
                for marker_name in unique_gait_markers:
                    marker_data = gait_markers.filter(pl.col("marker_name") == marker_name)
                    times = marker_data["time_seconds"].to_numpy()
                    heights = marker_data["z"].to_numpy()  # Vertical position
                    
                    fig.add_trace(go.Scatter(
                        x=times,
                        y=heights,
                        mode='lines',
                        name=f'{marker_name} Height',
                        hovertemplate=(
                            f"<b>{marker_name}</b><br>"
                            "Time: %{x:.3f} s<br>"
                            "Height: %{y:.1f} mm<br>"
                            "<extra></extra>"
                        )
                    ), row=2, col=1)
        
        # Add gait events if provided
        if gait_events:
            for event in gait_events:
                event_time = event.get('time', 0)
                event_type = event.get('type', 'Event')
                
                # Add vertical lines for gait events on each subplot
                for row in range(1, 4):
                    fig.add_vline(
                        x=event_time,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=event_type if row == 1 else "",
                        row=row, col=1
                    )
        
        # Update layout
        plot_title = title or f"Trial {trial.name or trial.id} - Gait Analysis"
        
        fig.update_xaxes(title_text="Time (s)")
        fig.update_yaxes(title_text="Force (N)", row=1, col=1)
        fig.update_yaxes(title_text="Height (mm)", row=2, col=1)
        fig.update_yaxes(title_text="Pattern", row=3, col=1)
        
        fig.update_layout(
            title=plot_title,
            height=800,
            **LAYOUT_DEFAULTS
        )
        
        if return_json:
            return {
                "data": json.loads(json.dumps(fig.to_dict()["data"], cls=PlotlyJSONEncoder)),
                "layout": json.loads(json.dumps(fig.to_dict()["layout"], cls=PlotlyJSONEncoder)),
                "config": PLOT_CONFIG
            }
        
        return fig
        
    except Exception as e:
        logger.error(f"Error in plot_gait_analysis: {str(e)}")
        if return_json:
            return {"error": str(e)}
        raise


# Backward compatibility functions for existing API endpoints
def plot_marker_trajectory_3d_legacy(
    markers_data: List[Dict],  # Legacy format
    **kwargs
) -> Union[go.Figure, Dict[str, Any]]:
    """Backward compatibility wrapper for legacy marker data format."""
    # This would convert legacy format to Trial object and call the new function
    # Implementation depends on specific legacy format
    raise NotImplementedError("Legacy format support not yet implemented")


def plot_force_plate_timeseries_legacy(
    force_plates_data: List[Dict],  # Legacy format
    **kwargs
) -> Union[go.Figure, Dict[str, Any]]:
    """Backward compatibility wrapper for legacy force plate data format."""
    # This would convert legacy format to Trial object and call the new function
    # Implementation depends on specific legacy format
    raise NotImplementedError("Legacy format support not yet implemented")


def plot_analog_signals_legacy(
    analogs_data: List[Dict],  # Legacy format
    **kwargs
) -> Union[go.Figure, Dict[str, Any]]:
    """Backward compatibility wrapper for legacy analog data format."""
    # This would convert legacy format to Trial object and call the new function
    # Implementation depends on specific legacy format
    raise NotImplementedError("Legacy format support not yet implemented")
