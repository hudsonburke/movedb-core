"""
Advanced 3D Trial Visualizer

This module creates comprehensive 3D trial visualizations similar to Vicon Nexus,
including force plates, force vectors as arrows, markers as spheres, and time scrubbing.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import numpy as np
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import timedelta
from sqlmodel import Session, select
import json
from plotly.utils import PlotlyJSONEncoder

from ..models.markers import Marker, MarkerData
from ..models.analogs import Analog, AnalogData
from ..models.forceplates import ForcePlate, ForcePlateData
from ..models.trial import Trial


def create_3d_trial_visualizer(
    session: Session,
    trial_id: int,
    current_time: float = 0.0,
    time_window: float = 0.1,  # Show data within this window (seconds)
    show_force_plates: bool = True,
    show_force_vectors: bool = True,
    show_markers: bool = True,
    show_trajectories: bool = True,
    trajectory_length: float = 1.0,  # Length of trajectory trails (seconds)
    force_scale: float = 0.001,  # Scale factor for force vectors
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
    
    try:
        fig = go.Figure()
        
        # Time range for current visualization
        current_td = timedelta(seconds=current_time)
        window_start = timedelta(seconds=max(0, current_time - time_window/2))
        window_end = timedelta(seconds=current_time + time_window/2)
        
        # Trail time range
        trail_start = timedelta(seconds=max(0, current_time - trajectory_length))
        
        # 1. Add Force Plates and Force Vectors
        if show_force_plates or show_force_vectors:
            force_plates = session.exec(
                select(ForcePlate).where(ForcePlate.trial_id == trial_id)
            ).all()
            
            for fp in force_plates:
                # Add force plate outline
                if show_force_plates:
                    plate_outline = create_force_plate_outline(fp)
                    fig.add_trace(plate_outline)
                
                # Add force vectors
                if show_force_vectors:
                    force_vectors = create_force_vectors(
                        session, fp, window_start, window_end, force_scale
                    )
                    for vector in force_vectors:
                        fig.add_trace(vector)
        
        # 2. Add Markers
        if show_markers or show_trajectories:
            markers = session.exec(
                select(Marker).where(Marker.trial_id == trial_id)
            ).all()
            
            for i, marker in enumerate(markers):
                color = px.colors.qualitative.Set1[i % len(px.colors.qualitative.Set1)]
                
                # Add current marker position as sphere
                if show_markers:
                    marker_sphere = create_marker_sphere(
                        session, marker, window_start, window_end, color, marker_size
                    )
                    if marker_sphere:
                        fig.add_trace(marker_sphere)
                
                # Add trajectory trail
                if show_trajectories:
                    trajectory = create_marker_trajectory(
                        session, marker, trail_start, current_td, color
                    )
                    if trajectory:
                        fig.add_trace(trajectory)
        
        # 3. Set up 3D scene with proper scaling and camera
        setup_3d_scene(fig, session, trial_id)
        
        # 4. Add time controls and layout
        setup_trial_visualizer_layout(fig, trial_id, current_time)
        
        if return_json:
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
        else:
            return fig
            
    except Exception as e:
        error_msg = f"Error creating 3D trial visualizer: {e}"
        if return_json:
            return {"error": error_msg}
        else:
            print(f"Warning: {error_msg}")
            return go.Figure()


def create_force_plate_outline(force_plate: ForcePlate) -> go.Scatter3d:
    """Create a 3D outline of a force plate."""
    
    # Default force plate dimensions (can be customized based on force_plate properties)
    # Typical force plate is around 400x600mm
    width = 0.4  # 400mm
    length = 0.6  # 600mm
    
    # Force plate center (assuming origin for now, can be customized)
    center_x = 0.0
    center_y = 0.0
    center_z = 0.0  # At ground level
    
    # Create rectangle outline
    x_coords = [
        center_x - width/2, center_x + width/2, center_x + width/2, 
        center_x - width/2, center_x - width/2
    ]
    y_coords = [
        center_y - length/2, center_y - length/2, center_y + length/2, 
        center_y + length/2, center_y - length/2
    ]
    z_coords = [center_z] * 5
    
    return go.Scatter3d(
        x=x_coords,
        y=y_coords,
        z=z_coords,
        mode='lines',
        line=dict(color='gray', width=4),
        name=f'Force Plate {force_plate.id}',
        showlegend=False,
        hovertemplate=f"Force Plate {force_plate.id}<extra></extra>"
    )


def create_force_vectors(
    session: Session, 
    force_plate: ForcePlate, 
    start_time: timedelta, 
    end_time: timedelta,
    scale: float
) -> List[go.Scatter3d]:
    """Create force vector arrows for a force plate."""
    
    # Get force plate data in time window
    fp_data = session.exec(
        select(ForcePlateData)
        .where(ForcePlateData.parent_id == force_plate.id)
        .where(ForcePlateData.timestamp >= start_time)
        .where(ForcePlateData.timestamp <= end_time)
        .order_by(ForcePlateData.timestamp)
    ).all()
    
    vectors = []
    
    for data in fp_data:
        # Force plate center (customize based on actual position)
        origin_x, origin_y, origin_z = 0.0, 0.0, 0.0
        
        # Force components (scale them for visualization)
        force_x = data.force_x * scale if data.force_x else 0
        force_y = data.force_y * scale if data.force_y else 0
        force_z = data.force_z * scale if data.force_z else 0
        
        # Skip very small forces
        force_magnitude = np.sqrt(force_x**2 + force_y**2 + force_z**2)
        if force_magnitude < 0.01:  # Minimum force threshold
            continue
        
        # Create arrow (line from origin to force endpoint)
        vector = go.Scatter3d(
            x=[origin_x, origin_x + force_x],
            y=[origin_y, origin_y + force_y],
            z=[origin_z, origin_z + force_z],
            mode='lines+markers',
            line=dict(color='red', width=6),
            marker=dict(
                size=[3, 8],  # Smaller at origin, larger at tip
                color=['red', 'darkred'],
                symbol=['circle', 'cone-up']
            ),
            showlegend=False,
            hovertemplate=(
                f"Force Vector<br>"
                f"Fx: {data.force_x:.1f} N<br>"
                f"Fy: {data.force_y:.1f} N<br>"
                f"Fz: {data.force_z:.1f} N<br>"
                f"Magnitude: {force_magnitude/scale:.1f} N<br>"
                "<extra></extra>"
            )
        )
        vectors.append(vector)
    
    return vectors


def create_marker_sphere(
    session: Session,
    marker: Marker,
    start_time: timedelta,
    end_time: timedelta,
    color: str,
    size: int
) -> Optional[go.Scatter3d]:
    """Create a marker sphere at current time position."""
    
    # Get marker data in time window (should be very small window for "current" position)
    marker_data = session.exec(
        select(MarkerData)
        .where(MarkerData.parent_id == marker.id)
        .where(MarkerData.timestamp >= start_time)
        .where(MarkerData.timestamp <= end_time)
        .order_by(MarkerData.timestamp)
    ).first()
    
    if not marker_data:
        return None
    
    return go.Scatter3d(
        x=[marker_data.x],
        y=[marker_data.y],
        z=[marker_data.z],
        mode='markers',
        marker=dict(
            size=size,
            color=color,
            symbol='circle',
            line=dict(color='black', width=1)
        ),
        name=marker.name,
        showlegend=True,
        hovertemplate=(
            f"<b>{marker.name}</b><br>"
            f"X: {marker_data.x:.3f} m<br>"
            f"Y: {marker_data.y:.3f} m<br>"
            f"Z: {marker_data.z:.3f} m<br>"
            "<extra></extra>"
        )
    )


def create_marker_trajectory(
    session: Session,
    marker: Marker,
    start_time: timedelta,
    end_time: timedelta,
    color: str
) -> Optional[go.Scatter3d]:
    """Create marker trajectory trail."""
    
    # Get marker data for trajectory
    trajectory_data = session.exec(
        select(MarkerData)
        .where(MarkerData.parent_id == marker.id)
        .where(MarkerData.timestamp >= start_time)
        .where(MarkerData.timestamp <= end_time)
        .order_by(MarkerData.timestamp)
    ).all()
    
    if len(trajectory_data) < 2:
        return None
    
    x_coords = [d.x for d in trajectory_data]
    y_coords = [d.y for d in trajectory_data]
    z_coords = [d.z for d in trajectory_data]
    
    return go.Scatter3d(
        x=x_coords,
        y=y_coords,
        z=z_coords,
        mode='lines',
        line=dict(
            color=color,
            width=3,
            # Add gradient effect (opacity decreases towards past)
        ),
        name=f'{marker.name} Trail',
        showlegend=False,
        hovertemplate=f"<b>{marker.name} Trail</b><extra></extra>"
    )


def setup_3d_scene(fig: go.Figure, session: Session, trial_id: int):
    """Set up the 3D scene with appropriate scaling and camera angle."""
    
    # Calculate scene bounds based on marker data
    markers = session.exec(
        select(Marker).where(Marker.trial_id == trial_id)
    ).all()
    
    all_x, all_y, all_z = [], [], []
    
    for marker in markers:
        marker_data = session.exec(
            select(MarkerData).where(MarkerData.parent_id == marker.id)
        ).all()
        
        for data in marker_data:
            all_x.append(data.x)
            all_y.append(data.y)
            all_z.append(data.z)
    
    if all_x:
        x_range = [min(all_x) - 0.5, max(all_x) + 0.5]
        y_range = [min(all_y) - 0.5, max(all_y) + 0.5]
        z_range = [min(all_z) - 0.2, max(all_z) + 0.5]
    else:
        x_range = [-1, 1]
        y_range = [-1, 1]
        z_range = [0, 2]
    
    fig.update_layout(
        scene=dict(
            xaxis=dict(
                title="X (m)",
                range=x_range,
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                title="Y (m)",
                range=y_range,
                showgrid=True,
                gridcolor='lightgray'
            ),
            zaxis=dict(
                title="Z (m)",
                range=z_range,
                showgrid=True,
                gridcolor='lightgray'
            ),
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=0.8),  # Slightly compressed Z for better viewing
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.2),  # Good viewing angle
                center=dict(x=0, y=0, z=0.5),
                up=dict(x=0, y=0, z=1)
            ),
            bgcolor='white'
        )
    )


def setup_trial_visualizer_layout(fig: go.Figure, trial_id: int, current_time: float):
    """Set up the layout for the trial visualizer with time controls."""
    
    fig.update_layout(
        title={
            'text': f"3D Trial Visualizer - Trial {trial_id} (Time: {current_time:.2f}s)",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16}
        },
        showlegend=True,
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='gray',
            borderwidth=1
        ),
        margin=dict(l=0, r=0, t=60, b=0),
        height=700,
        # Add time slider (this would be enhanced in the frontend)
        annotations=[
            dict(
                text=f"Time: {current_time:.2f}s",
                showarrow=False,
                x=0.02,
                y=0.02,
                xref='paper',
                yref='paper',
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='gray',
                borderwidth=1,
                font=dict(size=12)
            )
        ]
    )


def get_trial_time_bounds(session: Session, trial_id: int) -> Tuple[float, float]:
    """Get the time bounds for a trial."""
    
    # Get time bounds from marker data (assuming markers have the full time range)
    markers = session.exec(
        select(Marker).where(Marker.trial_id == trial_id)
    ).all()
    
    if not markers:
        return 0.0, 1.0
    
    min_time = float('inf')
    max_time = float('-inf')
    
    for marker in markers:
        marker_data = session.exec(
            select(MarkerData)
            .where(MarkerData.parent_id == marker.id)
            .order_by(MarkerData.timestamp)
        ).all()
        
        if marker_data:
            first_time = marker_data[0].timestamp.total_seconds()
            last_time = marker_data[-1].timestamp.total_seconds()
            min_time = min(min_time, first_time)
            max_time = max(max_time, last_time)
    
    return min_time if min_time != float('inf') else 0.0, max_time if max_time != float('-inf') else 1.0
