"""
MoveDB Plotting Module

Provides consistent biomechanical plotting functions that work in both
Jupyter notebooks and API contexts.
"""

from .biomech import (
    plot_marker_trajectory_3d,
    plot_force_plate_timeseries,
    plot_analog_signals,
    plot_gait_analysis,
    plot_trial_dashboard,
    plot_3d_trial_visualizer,
    get_trial_time_range,
    get_plot_config,
    BIOMECH_COLORS,
    PLOT_CONFIG,
    LAYOUT_DEFAULTS
)

__all__ = [
    'plot_marker_trajectory_3d',
    'plot_force_plate_timeseries', 
    'plot_analog_signals',
    'plot_gait_analysis',
    'plot_trial_dashboard',
    'plot_3d_trial_visualizer',
    'get_trial_time_range',
    'get_plot_config',
    'BIOMECH_COLORS',
    'PLOT_CONFIG',
    'LAYOUT_DEFAULTS'
]