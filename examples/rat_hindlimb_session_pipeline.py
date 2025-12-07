"""
Rat Hindlimb Session Configuration System
=========================================

Configuration system for reproducible rat hindlimb biomechanics analysis pipelines.
Supports YAML-based configuration with CLI overrides and automatic trial discovery.

Features:
- Pydantic-based configuration models with validation
- YAML configuration loading with CLI argument overrides
- Pattern-based trial discovery and filtering
- Comprehensive validation and error handling
- Support for static and dynamic trial configurations

Author: MoveDB Core
License: MIT
"""

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import json
import shutil

import yaml
import numpy as np
from loguru import logger
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from movedb.models import Trial
from movedb.ingest import C3DAdapter
from movedb.storage import set_storage_config, StorageConfig, HDF5TrialStorage
from movedb.osim import (
    IKSettings,
    IKResult,
    IDSettings,
    IDResult,
    CMCSettings,
    CMCResult,
)

# External RatHindlimb imports (assumed installed)
try:
    # Try direct import first (if installed as package)
    from RatHindlimb.scale_utils import scale_opensim_model
except ImportError:
    try:
        # Try local import from RatHindlimb directory
        import sys
        from pathlib import Path

        rat_repo_path = Path(__file__).parent.parent.parent / "RatHindlimb" / "src"
        sys.path.insert(0, str(rat_repo_path))
        from rathindlimb.scale_utils import scale_opensim_model
    except ImportError:
        logger.error(
            "RatHindlimb package not found. Please install it or ensure it's in the expected location."
        )
        raise


class StaticTrialConfig(BaseModel):
    """Configuration for static (calibration) trials."""

    name: str = Field(..., description="Trial name identifier")
    c3d_path: str = Field(..., description="Path to C3D file")
    time_range: tuple[float, float] | None = Field(
        default=None, description="Time range for analysis (start, end) in seconds"
    )
    marker_set: list[str] | None = Field(
        default=None, description="Required markers for this trial"
    )

    @field_validator("c3d_path")
    @classmethod
    def validate_c3d_path(cls, v: str) -> str:
        """Validate C3D file exists and has correct extension."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"C3D file does not exist: {v}")
        if path.suffix.lower() != ".c3d":
            raise ValueError(f"File must have .c3d extension: {v}")
        return str(path.absolute())


class DynamicTrialConfig(BaseModel):
    """Configuration for dynamic (movement) trials."""

    pattern: str = Field(..., description="Regex pattern to match trial names")
    c3d_directory: str = Field(..., description="Directory containing C3D files")
    exclude_patterns: list[str] | None = Field(
        default=None, description="Patterns to exclude from matching"
    )
    time_range: tuple[float, float] | None = Field(
        default=None,
        description="Default time range for analysis (start, end) in seconds",
    )
    marker_set: Optional[List[str]] = Field(
        default=None, description="Required markers for these trials"
    )

    @field_validator("c3d_directory")
    @classmethod
    def validate_c3d_directory(cls, v: str) -> str:
        """Validate C3D directory exists."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"C3D directory does not exist: {v}")
        if not path.is_dir():
            raise ValueError(f"Path must be a directory: {v}")
        return str(path.absolute())


class ScalePhaseResult(BaseModel):
    """Result of the scaling phase with all relevant paths and metadata."""

    trial_path: str = Field(..., description="Path to the input C3D trial file")
    hdf5_path: str = Field(..., description="Path to the HDF5 storage file")
    trc_path: str = Field(..., description="Path to the exported TRC marker file")
    scaled_model_path: str = Field(..., description="Path to the scaled OpenSim model")
    scaling_params_path: str = Field(
        ..., description="Path to the scaling parameters JSON"
    )
    provenance_path: str = Field(..., description="Path to the provenance JSON")
    limb_lengths: dict[str, float] = Field(..., description="Calculated limb lengths")
    time_range: Tuple[float, float] = Field(
        ..., description="Time range used for scaling"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp of creation"
    )


class DynamicTrialResult(BaseModel):
    """Result of processing a dynamic trial with IK and CMC."""

    trial_path: str = Field(..., description="Path to the input C3D trial file")
    hdf5_path: str = Field(..., description="Path to the HDF5 storage file")
    ik_result_path: str = Field(..., description="Path to the IK results")
    cmc_result_path: str = Field(..., description="Path to the CMC results")
    time_range: Tuple[float, float] = Field(
        ..., description="Time range used for analysis"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp of creation"
    )


class TrialProcessingResult(BaseModel):
    """Result of dynamic trial processing with all relevant paths and results."""

    trial_path: str = Field(..., description="Path to the input C3D trial file")
    hdf5_path: str = Field(..., description="Path to the HDF5 storage file")
    trc_path: str = Field(..., description="Path to the exported TRC marker file")
    grf_mot_path: str = Field(..., description="Path to the exported GRF MOT file")
    external_loads_xml_path: str = Field(
        ..., description="Path to the external loads XML file"
    )
    ik_result: IKResult = Field(
        ..., description="Result from Inverse Kinematics analysis"
    )
    id_result: IDResult = Field(
        ..., description="Result from Inverse Dynamics analysis"
    )
    cmc_result: CMCResult = Field(
        ..., description="Result from Computed Muscle Control analysis"
    )
    ik_settings_path: str = Field(..., description="Path to IK settings JSON")
    id_settings_path: str = Field(..., description="Path to ID settings JSON")
    cmc_settings_path: str = Field(..., description="Path to CMC settings JSON")
    provenance_path: str = Field(..., description="Path to processing provenance JSON")
    time_range: Tuple[float, float] = Field(
        ..., description="Time range used for processing"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp of creation"
    )


class SessionResult(BaseModel):
    """Complete result of running the session pipeline."""

    session_name: str = Field(..., description="Session name identifier")
    subject_id: str = Field(..., description="Subject identifier")
    output_directory: str = Field(..., description="Base output directory for results")
    scaling_result: ScalePhaseResult = Field(
        ..., description="Result from scaling phase"
    )
    dynamic_trial_results: List[TrialProcessingResult] = Field(
        default_factory=list, description="Results from processing dynamic trials"
    )
    documentation_path: str = Field(
        ..., description="Path to generated session documentation"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp of session completion"
    )
    success_count: int = Field(
        ..., description="Number of successfully processed dynamic trials"
    )
    failure_count: int = Field(..., description="Number of failed dynamic trials")


class SessionConfig(BaseModel):
    """Complete session configuration for rat hindlimb analysis."""

    # Session metadata
    name: str = Field(..., description="Session name identifier")
    subject_id: str = Field(..., description="Subject identifier")
    output_directory: str = Field(..., description="Base output directory for results")

    # Model file paths
    base_model: str = Field(..., description="Path to base OpenSim model file")
    marker_set: str = Field(..., description="Path to marker set XML file")
    task_set: Optional[str] = Field(
        default=None, description="Path to task set XML file"
    )
    actuators: Optional[str] = Field(
        default=None, description="Path to actuators XML file"
    )
    control_constraints: Optional[str] = Field(
        default=None, description="Path to control constraints XML file"
    )

    # Subject parameters
    mass: float = Field(..., description="Subject mass in kg", gt=0)

    # Trial configurations
    static_trials: List[StaticTrialConfig] = Field(
        default_factory=list, description="Static trial configurations"
    )
    dynamic_trials: List[DynamicTrialConfig] = Field(
        default_factory=list, description="Dynamic trial configurations"
    )

    # Processing parameters
    lowpass_cutoff: float = Field(
        default=6.0, description="Low-pass filter cutoff frequency in Hz", gt=0
    )
    ik_accuracy: float = Field(
        default=1e-5, description="Inverse kinematics accuracy", gt=0
    )
    cmc_time_window: float = Field(
        default=0.01, description="CMC time window in seconds", gt=0
    )

    # Force plate configuration
    body_mapping: Dict[str, str] = Field(
        default_factory=lambda: {"Left": "foot_l", "Right": "foot_r"},
        description="Mapping of force plate contexts to OpenSim body names",
    )

    # Required markers
    required_markers: List[str] = Field(
        default_factory=list, description="List of required marker names for validation"
    )

    @field_validator("output_directory")
    @classmethod
    def validate_output_directory(cls, v: str) -> str:
        """Validate and create output directory."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())

    @field_validator(
        "base_model", "marker_set", "task_set", "actuators", "control_constraints"
    )
    @classmethod
    def validate_file_paths(cls, v: Optional[str]) -> Optional[str]:
        """Validate file paths exist (when provided)."""
        if v is None:
            return v
        path = Path(v)
        if not path.exists():
            raise ValueError(f"File does not exist: {v}")
        return str(path.absolute())

    @model_validator(mode="after")
    def validate_trial_configurations(self) -> "SessionConfig":
        """Validate that at least one trial configuration is provided."""
        if not self.static_trials and not self.dynamic_trials:
            raise ValueError(
                "At least one static or dynamic trial configuration must be provided"
            )
        return self


def load_yaml_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary containing configuration data

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info(f"Loading configuration from {config_path}")
    with open(config_file, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    if not isinstance(config_data, dict):
        raise ValueError(
            f"Configuration file must contain a dictionary, got {type(config_data)}"
        )

    return config_data


def create_session_config(
    config_data: Dict[str, Any], cli_overrides: Optional[Dict[str, Any]] = None
) -> SessionConfig:
    """
    Create SessionConfig from dictionary data with optional CLI overrides.

    Args:
        config_data: Base configuration dictionary
        cli_overrides: Optional CLI argument overrides

    Returns:
        Validated SessionConfig instance

    Raises:
        ValidationError: If configuration is invalid
    """
    # Apply CLI overrides
    if cli_overrides:
        config_data = {**config_data, **cli_overrides}
        logger.info("Applied CLI overrides to configuration")

    try:
        config = SessionConfig(**config_data)
        logger.success("Configuration validation successful")
        return config
    except ValidationError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise


def discover_trials(config: SessionConfig) -> Dict[str, List[str]]:
    """
    Discover trials based on configuration patterns.

    Args:
        config: Session configuration

    Returns:
        Dictionary mapping trial types to lists of discovered trial paths

    Raises:
        ValueError: If no trials are discovered or validation fails
    """
    discovered_trials = {"static": [], "dynamic": []}

    # Process static trials
    for static_trial in config.static_trials:
        logger.info(f"Validating static trial: {static_trial.name}")
        discovered_trials["static"].append(static_trial.c3d_path)

    # Process dynamic trials
    for dynamic_config in config.dynamic_trials:
        logger.info(f"Discovering dynamic trials in {dynamic_config.c3d_directory}")
        c3d_dir = Path(dynamic_config.c3d_directory)
        pattern = re.compile(dynamic_config.pattern)

        # Collect all C3D files
        c3d_files = list(c3d_dir.glob("*.c3d"))

        if not c3d_files:
            logger.warning(f"No C3D files found in {c3d_dir}")
            continue

        # Filter by pattern
        matched_files = []
        for c3d_file in c3d_files:
            trial_name = c3d_file.stem

            # Check if matches pattern
            if not pattern.match(trial_name):
                continue

            # Check exclude patterns
            excluded = False
            if dynamic_config.exclude_patterns:
                for exclude_pattern in dynamic_config.exclude_patterns:
                    if re.match(exclude_pattern, trial_name):
                        excluded = True
                        break

            if not excluded:
                matched_files.append(str(c3d_file))

        if matched_files:
            logger.success(
                f"Discovered {len(matched_files)} dynamic trials matching '{dynamic_config.pattern}'"
            )
            discovered_trials["dynamic"].extend(matched_files)
        else:
            logger.warning(
                f"No trials matched pattern '{dynamic_config.pattern}' in {c3d_dir}"
            )

    # Validate that we have some trials
    total_trials = len(discovered_trials["static"]) + len(discovered_trials["dynamic"])
    if total_trials == 0:
        raise ValueError(
            "No trials discovered. Check your trial configurations and file paths."
        )

    logger.info(
        f"Total trials discovered: {total_trials} "
        f"(static: {len(discovered_trials['static'])}, "
        f"dynamic: {len(discovered_trials['dynamic'])})"
    )

    return discovered_trials


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create command-line argument parser supporting YAML config and direct overrides.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Rat Hindlimb Session Configuration System",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Configuration file
    parser.add_argument("--config", type=str, help="Path to YAML configuration file")

    # Session metadata overrides
    parser.add_argument("--name", type=str, help="Session name identifier")
    parser.add_argument("--subject-id", type=str, help="Subject identifier")
    parser.add_argument(
        "--output-directory", type=str, help="Base output directory for results"
    )

    # Model file overrides
    parser.add_argument(
        "--base-model", type=str, help="Path to base OpenSim model file"
    )
    parser.add_argument("--marker-set", type=str, help="Path to marker set XML file")
    parser.add_argument("--mass", type=float, help="Subject mass in kg")

    # Processing parameter overrides
    parser.add_argument(
        "--lowpass-cutoff", type=float, help="Low-pass filter cutoff frequency in Hz"
    )
    parser.add_argument("--ik-accuracy", type=float, help="Inverse kinematics accuracy")

    # Output options
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Only validate configuration, do not run analysis",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    return parser


def parse_cli_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Extract CLI overrides from parsed arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Dictionary of configuration overrides
    """
    overrides = {}

    # Map CLI args to config keys
    arg_mapping = {
        "name": "name",
        "subject_id": "subject_id",
        "output_directory": "output_directory",
        "base_model": "base_model",
        "marker_set": "marker_set",
        "mass": "mass",
        "lowpass_cutoff": "lowpass_cutoff",
        "ik_accuracy": "ik_accuracy",
    }

    for arg_name, config_key in arg_mapping.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            overrides[config_key] = value

    return overrides


def validate_configuration(config: SessionConfig) -> bool:
    """
    Perform additional validation beyond Pydantic models.

    Args:
        config: Session configuration to validate

    Returns:
        True if validation passes

    Raises:
        ValueError: If validation fails
    """
    logger.info("Performing additional configuration validation")

    # Validate required markers are reasonable
    if config.required_markers:
        if len(config.required_markers) < 3:
            logger.warning(
                "Very few required markers specified. This may cause issues with model scaling."
            )

        # Check for duplicates
        if len(config.required_markers) != len(set(config.required_markers)):
            raise ValueError("Required markers list contains duplicates")

    # Validate processing parameters are reasonable
    if config.lowpass_cutoff > 50:
        logger.warning(
            f"Low-pass cutoff frequency ({config.lowpass_cutoff} Hz) seems high for biomechanics data"
        )

    if config.ik_accuracy > 1e-3:
        logger.warning(
            f"IK accuracy ({config.ik_accuracy}) may be too low for convergence"
        )

    # Validate body mapping
    if not config.body_mapping:
        raise ValueError("Body mapping cannot be empty")

    logger.success("Additional validation passed")
    return True


def calculate_rat_limb_lengths(
    trial: Trial, time_range: Tuple[float, float] | None = None
) -> Dict[str, float]:
    """
    Calculate segment lengths for rat hindlimb using anatomical markers.

    Calculates lengths for femur, tibia, and foot segments on both left and right
    sides using marker trajectories. Handles invalid marker frames by averaging
    over valid frames only.

    Args:
        trial: Trial object with loaded marker data
        time_range: Optional time range (start, end) in seconds to restrict calculation.
                   If None, uses all frames.

    Returns:
        Dictionary with segment lengths in millimeters:
        {
            'right_femur': length_mm,
            'left_femur': length_mm,
            'right_tibia': length_mm,
            'left_tibia': length_mm,
            'right_foot': length_mm,
            'left_foot': length_mm
        }

    Raises:
        ValueError: If required markers are missing or no valid frames found

    Example:
        >>> trial = Trial.get(session, trial_id)
        >>> lengths = calculate_rat_limb_lengths(trial, time_range=(1.0, 5.0))
        >>> print(f"Right femur: {lengths['right_femur']:.1f} mm")
    """
    # Define required markers and segments
    required_markers = ["RHIP", "RKNE", "RANK", "RTOE", "LHIP", "LKNE", "LANK", "LTOE"]

    segments = {
        "right_femur": ("RHIP", "RKNE"),
        "left_femur": ("LHIP", "LKNE"),
        "right_tibia": ("RKNE", "RANK"),
        "left_tibia": ("LKNE", "LANK"),
        "right_foot": ("RANK", "RTOE"),
        "left_foot": ("LANK", "LTOE"),
    }

    # Load marker data
    try:
        marker_data = trial.load_markers()
        markers_array = marker_data["data"]  # Shape: (n_frames, n_markers, 3)
        marker_names = marker_data["marker_names"]
        marker_rate = marker_data["rate"]
    except Exception as e:
        raise ValueError(f"Failed to load marker data from trial: {e}")

    # Restrict to time range if provided
    if time_range is not None:
        start_frame = int(time_range[0] * marker_rate)
        end_frame = int(time_range[1] * marker_rate)
        n_frames = markers_array.shape[0]
        start_frame = max(0, min(start_frame, n_frames - 1))
        end_frame = max(0, min(end_frame, n_frames - 1))
        if start_frame < end_frame:
            markers_array = markers_array[start_frame : end_frame + 1]
            logger.info(
                f"Restricted calculation to frames {start_frame}-{end_frame} ({time_range[0]:.2f}-{time_range[1]:.2f}s)"
            )
        else:
            logger.warning(f"Invalid time range {time_range}, using all frames")

    # Validate required markers exist
    missing_markers = []
    marker_indices = {}

    for marker in required_markers:
        try:
            idx = marker_names.index(marker)
            marker_indices[marker] = idx
        except ValueError:
            missing_markers.append(marker)

    if missing_markers:
        available_markers = ", ".join(marker_names)
        raise ValueError(
            f"Required markers not found in trial '{trial.name}': {missing_markers}. "
            f"Available markers: {available_markers}"
        )

    logger.info(f"Calculating limb lengths for trial '{trial.name}'")

    lengths = {}

    for segment_name, (proximal_marker, distal_marker) in segments.items():
        # Get marker data
        prox_idx = marker_indices[proximal_marker]
        dist_idx = marker_indices[distal_marker]

        prox_data = markers_array[:, prox_idx, :]  # (n_frames, 3)
        dist_data = markers_array[:, dist_idx, :]  # (n_frames, 3)

        # Find valid frames where both markers are valid
        # Valid means not NaN and not -9999.0 (sentinel value)
        prox_valid = ((prox_data != -9999.0) & (~np.isnan(prox_data))).all(
            axis=1
        )  # Shape: (n_frames,)

        dist_valid = ((dist_data != -9999.0) & (~np.isnan(dist_data))).all(
            axis=1
        )  # Shape: (n_frames,)

        valid_frames = prox_valid & dist_valid

        if not valid_frames.any():
            raise ValueError(
                f"No valid frames found for segment {segment_name} "
                f"({proximal_marker} -> {distal_marker}) in trial '{trial.name}'"
            )

        # Calculate distances for valid frames
        valid_prox = prox_data[valid_frames]  # (n_valid_frames, 3)
        valid_dist = dist_data[valid_frames]  # (n_valid_frames, 3)

        # Euclidean distance between markers
        distances = np.linalg.norm(valid_prox - valid_dist, axis=1)  # (n_valid_frames,)

        # Average distance across valid frames
        mean_distance_m = np.mean(distances)

        # Convert to millimeters
        mean_distance_mm = mean_distance_m * 1000.0

        lengths[segment_name] = mean_distance_mm

        logger.debug(
            f"{segment_name}: {mean_distance_mm:.2f} mm "
            f"({valid_frames.sum()}/{len(valid_frames)} valid frames)"
        )

    logger.success(
        f"Calculated limb lengths for trial '{trial.name}': "
        f"R femur={lengths['right_femur']:.1f}mm, "
        f"L femur={lengths['left_femur']:.1f}mm, "
        f"R tibia={lengths['right_tibia']:.1f}mm, "
        f"L tibia={lengths['left_tibia']:.1f}mm, "
        f"R foot={lengths['right_foot']:.1f}mm, "
        f"L foot={lengths['left_foot']:.1f}mm"
    )

    return lengths


def extract_time_range_from_events(
    trial: Trial, required_markers: list[str] | None = None
) -> tuple[float, float]:
    """
    Extract time range from first event to last event and validate marker presence.

    Takes a Trial object with events loaded, extracts the time range from the first
    to last event, and validates that required markers are present in all frames
    within that time range.

    Args:
        trial: Trial object with events loaded
        required_markers: List of marker names that must be valid throughout the range.
                          If None, uses default rat hindlimb markers for IK analysis.

    Returns:
        Tuple of (start_time, end_time) in seconds

    Raises:
        ValueError: If no events found or critical markers missing from trial

    Example:
        >>> trial = Trial.get(session, trial_id)
        >>> start_time, end_time = extract_time_range_from_events(trial)
        >>> print(f"Analysis range: {start_time:.2f}s - {end_time:.2f}s")
    """
    # Default required markers for rat hindlimb IK analysis
    if required_markers is None:
        required_markers = [
            "RASI",
            "RHIP",
            "RKNE",
            "RANK",
            "RTOE",
            "TAIL",
            "LHIP",
            "LKNE",
            "LANK",
            "LTOE",
        ]

    # Check if trial has events
    if not trial.events:
        raise ValueError(f"No events found in trial '{trial.name}'")

    # Sort events by time
    sorted_events = sorted(
        trial.events, key=lambda e: e.get_time(trial.marker_rate).total_seconds()
    )

    # Get first and last events
    first_event = sorted_events[0]
    last_event = sorted_events[-1]

    # Get times in seconds
    start_time = first_event.get_time(trial.marker_rate).total_seconds()
    end_time = last_event.get_time(trial.marker_rate).total_seconds()

    logger.info(
        f"Extracted time range from events in trial '{trial.name}': "
        f"{start_time:.3f}s - {end_time:.3f}s "
        f"(first: {first_event.label}@{first_event.context}, "
        f"last: {last_event.label}@{last_event.context})"
    )

    # Load marker data
    try:
        marker_data = trial.load_markers()
        markers_array = marker_data["data"]  # Shape: (n_frames, n_markers, 3)
        marker_names = marker_data["marker_names"]
        marker_rate = marker_data["rate"]
    except Exception as e:
        raise ValueError(f"Failed to load marker data from trial '{trial.name}': {e}")

    # Validate required markers exist in trial
    missing_markers = []
    marker_indices = []
    for marker in required_markers:
        try:
            idx = marker_names.index(marker)
            marker_indices.append(idx)
        except ValueError:
            missing_markers.append(marker)

    if missing_markers:
        available_markers = ", ".join(marker_names)
        raise ValueError(
            f"Required markers not found in trial '{trial.name}': {missing_markers}. "
            f"Available markers: {available_markers}"
        )

    # Convert time range to frame range
    start_frame = int(start_time * marker_rate)
    end_frame = int(end_time * marker_rate)

    # Ensure frame range is within trial bounds
    n_frames = markers_array.shape[0]
    start_frame = max(0, min(start_frame, n_frames - 1))
    end_frame = max(0, min(end_frame, n_frames - 1))

    if start_frame >= end_frame:
        raise ValueError(
            f"Invalid frame range in trial '{trial.name}': "
            f"start_frame={start_frame}, end_frame={end_frame}"
        )

    logger.info(
        f"Validating {len(required_markers)} markers in frame range "
        f"{start_frame}-{end_frame} ({end_frame - start_frame + 1} frames)"
    )

    # Extract markers for the required ones
    required_markers_array = markers_array[
        :, marker_indices, :
    ]  # (n_frames, n_required, 3)

    # Check validity for each frame in range
    # Valid means not NaN and not -9999.0
    is_valid_marker = (
        (required_markers_array != -9999.0) & (~np.isnan(required_markers_array))
    ).all(axis=2)  # Shape: (n_frames, n_required)

    # Frame is valid if ALL required markers are valid
    is_valid_frame = is_valid_marker.all(axis=1)  # Shape: (n_frames,)

    # Check frames in the range
    range_frames = np.arange(start_frame, end_frame + 1)
    valid_in_range = is_valid_frame[range_frames]

    # Count invalid frames
    invalid_frames = (~valid_in_range).sum()
    total_frames = len(range_frames)

    if invalid_frames > 0:
        invalid_percent = (invalid_frames / total_frames) * 100
        logger.warning(
            f"Found {invalid_frames}/{total_frames} ({invalid_percent:.1f}%) "
            f"invalid frames in time range for trial '{trial.name}'. "
            f"Marker validation will continue but analysis may be affected."
        )

        # Log which markers are invalid in which frames (first few examples)
        invalid_frame_indices = range_frames[~valid_in_range][
            :5
        ]  # First 5 invalid frames
        for frame_idx in invalid_frame_indices:
            invalid_markers_in_frame = []
            for i, marker_name in enumerate(required_markers):
                if not is_valid_marker[frame_idx, i]:
                    invalid_markers_in_frame.append(marker_name)
            frame_time = frame_idx / marker_rate
            logger.warning(
                f"Frame {frame_idx} ({frame_time:.3f}s): "
                f"Invalid markers: {invalid_markers_in_frame}"
            )

    else:
        logger.success(
            f"All {total_frames} frames in time range are valid for "
            f"all {len(required_markers)} required markers"
        )

    return start_time, end_time


def run_scaling_phase(
    c3d_path: str,
    output_dir: str,
    subject_id: str = "rat_01",
    trial_name: str = "static",
) -> ScalePhaseResult:
    """
    Run the complete scaling phase for rat hindlimb analysis.

    Args:
        c3d_path: Path to the static C3D trial file
        output_dir: Directory for outputs
        subject_id: Subject identifier
        trial_name: Trial name

    Returns:
        ScalePhaseResult with all paths and metadata
    """
    logger.info(f"Starting scaling phase for {subject_id}/{trial_name}")

    # Setup output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Configure storage
    hdf5_path = output_path / f"{subject_id}_{trial_name}.h5"
    config = StorageConfig(
        hdf5_base_dir=str(output_path),
        database_url=f"sqlite:///{output_path / 'analysis.db'}",
    )
    set_storage_config(config)

    # 1. Load static C3D trial using C3DAdapter
    logger.info(f"Loading C3D data from {c3d_path}")
    adapter = C3DAdapter.from_file(c3d_path, extract_forceplat_data=False)
    trial = adapter.to_trial()
    trial.name = trial_name

    # Save to HDF5
    storage = HDF5TrialStorage(str(hdf5_path))
    storage.write_trial_metadata(trial)
    storage.write_markers(adapter.get_marker_data())
    storage.write_events(trial.events)
    trial.storage_path = str(hdf5_path)
    trial.id = 1  # Dummy ID for loading
    logger.success(f"Trial saved to HDF5: {hdf5_path}")

    # 2. Extract time range from events
    time_range = extract_time_range_from_events(trial)

    # 3. Calculate limb lengths
    limb_lengths = calculate_rat_limb_lengths(trial, time_range)

    # 4. Export markers to TRC format
    trc_path = output_path / f"{trial_name}_markers.trc"
    trial.export_to_trc(str(trc_path), output_units="m")
    logger.success(f"Markers exported to TRC: {trc_path}")

    # 5. Handle path issue for scale_utils.py
    # scale_utils expects marker file in same directory, so copy TRC there
    # Assuming RatHindlimb is in a known location, or copy to current dir
    scale_dir = Path.cwd()  # Assume running in RatHindlimb directory
    scaled_trc_path = scale_dir / f"{trial_name}_markers.trc"
    shutil.copy2(trc_path, scaled_trc_path)
    logger.info(f"Copied TRC to scale directory: {scaled_trc_path}")

    # 6. Call scale_opensim_model from RatHindlimb
    logger.info("Running OpenSim scaling")
    scaled_model_path = scale_opensim_model(
        marker_file=str(scaled_trc_path),
        time_range=time_range,
        limb_lengths=limb_lengths,
        output_dir=str(output_path),
    )
    logger.success(f"Scaled model created: {scaled_model_path}")

    # 7. Save scaling parameters and provenance JSON
    scaling_params = {
        "subject_id": subject_id,
        "trial_name": trial_name,
        "c3d_source": str(c3d_path),
        "time_range": time_range,
        "limb_lengths": limb_lengths,
        "marker_file": str(trc_path),
        "scaled_model": str(scaled_model_path),
        "created_at": datetime.now().isoformat(),
    }

    scaling_params_path = output_path / f"{trial_name}_scaling_params.json"
    with open(scaling_params_path, "w") as f:
        json.dump(scaling_params, f, indent=2)
    logger.success(f"Scaling parameters saved: {scaling_params_path}")

    provenance = {
        "phase": "scaling",
        "inputs": {
            "c3d_file": str(c3d_path),
            "marker_file": str(trc_path),
        },
        "outputs": {
            "scaled_model": str(scaled_model_path),
            "scaling_params": str(scaling_params_path),
        },
        "parameters": scaling_params,
        "execution": {
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
        },
    }

    provenance_path = output_path / f"{trial_name}_scaling_provenance.json"
    with open(provenance_path, "w") as f:
        json.dump(provenance, f, indent=2)
    logger.success(f"Provenance saved: {provenance_path}")

    # 8. Return ScalePhaseResult
    result = ScalePhaseResult(
        trial_path=str(c3d_path),
        hdf5_path=str(hdf5_path),
        trc_path=str(trc_path),
        scaled_model_path=str(scaled_model_path),
        scaling_params_path=str(scaling_params_path),
        provenance_path=str(provenance_path),
        limb_lengths=limb_lengths,
        time_range=time_range,
    )

    logger.success("Scaling phase completed successfully")
    return result


def process_dynamic_trial(
    c3d_path: str,
    scaling_result: ScalePhaseResult,
    output_dir: str,
    config: SessionConfig,
    trial_name: str = "dynamic",
) -> TrialProcessingResult:
    """
    Process a dynamic trial with complete OpenSim analysis pipeline.

    Args:
        c3d_path: Path to the dynamic C3D trial file
        scaling_result: Result from scaling phase with scaled model path
        output_dir: Directory for outputs
        config: Session configuration
        trial_name: Trial name

    Returns:
        TrialProcessingResult with all paths and results
    """
    logger.info(f"Starting dynamic trial processing for {trial_name}")

    # Setup output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Configure storage
    hdf5_path = output_path / f"{config.subject_id}_{trial_name}.h5"
    storage_config = StorageConfig(
        hdf5_base_dir=str(output_path),
        database_url=f"sqlite:///{output_path / 'analysis.db'}",
    )
    set_storage_config(storage_config)

    # 1. Load dynamic C3D trial using C3DAdapter
    logger.info(f"Loading C3D data from {c3d_path}")
    adapter = C3DAdapter.from_file(c3d_path, extract_forceplat_data=True)
    trial = adapter.to_trial()
    trial.name = trial_name

    # Save to HDF5
    storage = HDF5TrialStorage(str(hdf5_path))
    storage.write_trial_metadata(trial)
    storage.write_markers(adapter.get_marker_data())
    storage.write_events(trial.events)
    storage.write_force_plates(adapter.get_force_plate_data())
    trial.storage_path = str(hdf5_path)
    trial.id = 1  # Dummy ID for loading
    logger.success(f"Trial saved to HDF5: {hdf5_path}")

    # 2. Extract time range from events using extract_time_range_from_events()
    time_range = extract_time_range_from_events(trial, config.required_markers)

    # 3. Export markers to TRC
    trc_path = output_path / f"{trial_name}_markers.trc"
    trial.export_to_trc(str(trc_path), output_units="m")
    logger.success(f"Markers exported to TRC: {trc_path}")

    # 4. Export forceplates to MOT/XML using export_external_loads_for_id()
    # Assume ENF file is in the same directory as C3D
    c3d_dir = Path(c3d_path).parent
    enf_path = c3d_dir / f"{Path(c3d_path).stem}.Trial.enf"
    if not enf_path.exists():
        # Try alternative naming
        enf_path = c3d_dir / f"{trial_name}.Trial.enf"
    if not enf_path.exists():
        raise FileNotFoundError(
            f"ENF file not found for trial {trial_name}. Expected at {enf_path}"
        )

    grf_mot_path, external_loads_xml_path = trial.export_external_loads_for_id(
        enf_path=str(enf_path),
        output_dir=str(output_path),
        body_mapping=config.body_mapping,
        mot_filename=f"{trial_name}_grf.mot",
        xml_filename=f"{trial_name}_external_loads.xml",
    )
    logger.success(
        f"Forceplates exported to MOT/XML: {grf_mot_path}, {external_loads_xml_path}"
    )

    # 5. Run IK using marker model from scaling phase
    logger.info("Running Inverse Kinematics")
    ik_settings = IKSettings(
        model_file=scaling_result.scaled_model_path,
        marker_file=str(trc_path),
        output_motion_file=str(output_path / f"{trial_name}_ik.mot"),
        results_directory=str(output_path),
        accuracy=config.ik_accuracy,
    )
    ik_result = ik_settings.run()
    logger.success(f"IK completed: {ik_result.output_motion_file}")

    # 6. Run ID using IK results and external loads
    logger.info("Running Inverse Dynamics")
    id_settings = IDSettings(
        model_file=scaling_result.scaled_model_path,
        coordinates_file=ik_result.output_motion_file,
        output_forces_file=str(output_path / f"{trial_name}_id.sto"),
        results_directory=str(output_path),
        external_loads_file=external_loads_xml_path,
        lowpass_cutoff_frequency=config.lowpass_cutoff,
        initial_time=time_range[0],
        final_time=time_range[1],
    )
    id_result = id_settings.run()
    logger.success(f"ID completed: {id_result.output_forces_file}")

    # 7. Run CMC using IK kinematics and task/actuator files
    logger.info("Running CMC analysis...")
    cmc_settings = CMCSettings(
        model_file=scaling_result.scaled_model_path,
        results_directory=str(output_path),
        initial_time=time_range[0],
        final_time=time_range[1],
        external_loads_file=external_loads_xml_path,
        force_set_files=[config.actuators] if config.actuators else [],
        desired_kinematics_file=ik_result.output_motion_file,
        task_set_file=config.task_set,
        constraints_file=config.control_constraints,
        cmc_time_window=config.cmc_time_window,
    )
    cmc_result = cmc_settings.run()
    logger.success(f"CMC completed: {cmc_result.output_controls_file}")

    # 8. Save all settings JSON
    ik_settings_path = output_path / f"{trial_name}_ik_settings.json"
    ik_settings.save_json(str(ik_settings_path))

    id_settings_path = output_path / f"{trial_name}_id_settings.json"
    id_settings.save_json(str(id_settings_path))

    cmc_settings_path = output_path / f"{trial_name}_cmc_settings.json"
    cmc_settings.save_json(str(cmc_settings_path))

    # 9. Record analysis in trial history
    trial.analysis_history.append(
        {
            "tool": "ik",
            "timestamp": datetime.now().isoformat(),
            "settings": str(ik_settings_path),
            "result": ik_result.output_motion_file,
        }
    )
    trial.analysis_history.append(
        {
            "tool": "id",
            "timestamp": datetime.now().isoformat(),
            "settings": str(id_settings_path),
            "result": id_result.output_forces_file,
        }
    )
    trial.analysis_history.append(
        {
            "tool": "cmc",
            "timestamp": datetime.now().isoformat(),
            "settings": str(cmc_settings_path),
            "result": cmc_result.output_controls_file,
        }
    )

    # 10. Save provenance files
    provenance = {
        "phase": "dynamic_trial_processing",
        "trial_name": trial_name,
        "inputs": {
            "c3d_file": str(c3d_path),
            "scaled_model": scaling_result.scaled_model_path,
            "enf_file": str(enf_path),
            "scaling_result": scaling_result.model_dump()
            if hasattr(scaling_result, "model_dump")
            else str(scaling_result),
        },
        "outputs": {
            "hdf5_file": str(hdf5_path),
            "trc_file": str(trc_path),
            "grf_mot_file": grf_mot_path,
            "external_loads_xml": external_loads_xml_path,
            "ik_motion": ik_result.output_motion_file,
            "id_forces": id_result.output_forces_file,
            "cmc_controls": cmc_result.output_controls_file,
            "ik_settings": str(ik_settings_path),
            "id_settings": str(id_settings_path),
            "cmc_settings": str(cmc_settings_path),
        },
        "parameters": {
            "time_range": time_range,
            "ik_accuracy": config.ik_accuracy,
            "lowpass_cutoff": config.lowpass_cutoff,
            "cmc_time_window": config.cmc_time_window,
        },
        "execution": {
            "started_at": ik_result.start_time.isoformat(),
            "completed_at": cmc_result.end_time.isoformat(),
        },
    }

    provenance_path = output_path / f"{trial_name}_processing_provenance.json"
    with open(provenance_path, "w") as f:
        json.dump(provenance, f, indent=2)
    logger.success(f"Provenance saved: {provenance_path}")

    # 11. Return TrialProcessingResult
    result = TrialProcessingResult(
        trial_path=str(c3d_path),
        hdf5_path=str(hdf5_path),
        trc_path=str(trc_path),
        grf_mot_path=grf_mot_path,
        external_loads_xml_path=external_loads_xml_path,
        ik_result=ik_result,
        id_result=id_result,
        cmc_result=cmc_result,
        ik_settings_path=str(ik_settings_path),
        id_settings_path=str(id_settings_path),
        cmc_settings_path=str(cmc_settings_path),
        provenance_path=str(provenance_path),
        time_range=time_range,
    )

    logger.success(f"Dynamic trial {trial_name} processing completed successfully")
    return result


def generate_session_documentation(
    config: SessionConfig, session_result: SessionResult, output_dir: str
) -> str:
    """
    Generate comprehensive session documentation.

    Args:
        session_result: Complete session results
        output_dir: Output directory

    Returns:
        Path to the generated documentation file
    """
    logger.info("Generating session documentation")

    output_path = Path(output_dir)
    doc_path = output_path / f"{session_result.session_name}_documentation.md"

    # Create documentation content
    content = f"""# Rat Hindlimb Session Analysis Report

## Session Information
- **Session Name**: {session_result.session_name}
- **Subject ID**: {session_result.subject_id}
- **Output Directory**: {session_result.output_directory}
- **Created At**: {session_result.created_at.isoformat()}

## Scaling Phase Results
- **Input Trial**: {session_result.scaling_result.trial_path}
- **Scaled Model**: {session_result.scaling_result.scaled_model_path}
- **Time Range**: {session_result.scaling_result.time_range[0]:.2f}s - {session_result.scaling_result.time_range[1]:.2f}s

### Limb Lengths (mm)
"""
    for segment, length in session_result.scaling_result.limb_lengths.items():
        content += f"- {segment}: {length:.2f}\n"

    content += f"""

## Dynamic Trial Results
- **Total Trials**: {len(session_result.dynamic_trial_results)}
- **Successful**: {session_result.success_count}
- **Failed**: {session_result.failure_count}

"""

    for i, trial_result in enumerate(session_result.dynamic_trial_results, 1):
        content += f"""### Trial {i}: {Path(trial_result.trial_path).stem}
- **Input Trial**: {trial_result.trial_path}
- **Time Range**: {trial_result.time_range[0]:.2f}s - {trial_result.time_range[1]:.2f}s
- **IK Results**: {trial_result.ik_result_path}
- **CMC Results**: {trial_result.cmc_result_path}

"""

    # Write to file
    with open(doc_path, "w") as f:
        f.write(content)

    logger.success(f"Session documentation generated: {doc_path}")
    return str(doc_path)


def run_session_pipeline(
    config: SessionConfig, discovered_trials: Dict[str, List[str]]
) -> SessionResult:
    """
    Run the complete session pipeline for rat hindlimb analysis.

    Args:
        config: Session configuration
        discovered_trials: Dictionary of discovered trial paths

    Returns:
        SessionResult with complete session metadata
    """
    logger.info(f"Starting session pipeline for {config.name}")

    # Phase 1: Setup session directory structure
    session_output_dir = Path(config.output_directory) / config.name
    session_output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Session output directory: {session_output_dir}")

    # Create subdirectories
    scaling_dir = session_output_dir / "scaling"
    dynamic_dir = session_output_dir / "dynamic"
    docs_dir = session_output_dir / "docs"
    scaling_dir.mkdir(exist_ok=True)
    dynamic_dir.mkdir(exist_ok=True)
    docs_dir.mkdir(exist_ok=True)

    success_count = 0
    failure_count = 0
    dynamic_results = []

    # Phase 2: Run scaling phase
    logger.info("=== PHASE 1: Scaling Phase ===")
    if not discovered_trials["static"]:
        raise ValueError("No static trials found for scaling phase")

    static_trial_path = discovered_trials["static"][0]  # Use first static trial
    scaling_result = run_scaling_phase(
        c3d_path=static_trial_path,
        output_dir=str(scaling_dir),
        subject_id=config.subject_id,
        trial_name="static",
    )

    # Phase 3: Process dynamic trials
    logger.info("=== PHASE 2: Dynamic Trial Processing ===")
    for i, dynamic_trial_path in enumerate(discovered_trials["dynamic"], 1):
        trial_name = f"dynamic_{i:02d}"
        logger.info(
            f"Processing dynamic trial {i}/{len(discovered_trials['dynamic'])}: {trial_name}"
        )

        try:
            trial_result = process_dynamic_trial(
                c3d_path=dynamic_trial_path,
                scaling_result=scaling_result,
                output_dir=str(dynamic_dir / trial_name),
                config=config,
                trial_name=trial_name,
            )
            dynamic_results.append(trial_result)
            success_count += 1
            logger.success(f"Successfully processed {trial_name}")

        except Exception as e:
            logger.error(f"Failed to process {trial_name}: {e}")
            failure_count += 1
            # Continue processing other trials

    # Phase 4: Generate session documentation
    logger.info("=== PHASE 3: Documentation Generation ===")
    session_result = SessionResult(
        session_name=config.name,
        subject_id=config.subject_id,
        output_directory=str(session_output_dir),
        scaling_result=scaling_result,
        dynamic_trial_results=dynamic_results,
        success_count=success_count,
        failure_count=failure_count,
    )

    generate_session_documentation_comprehensive(config, session_result, str(docs_dir))
    session_result.documentation_path = str(Path(docs_dir) / "README.md")

    logger.success("Session pipeline completed")
    logger.info(
        f"Processed {success_count} trials successfully, {failure_count} failed"
    )

    return session_result


def main():
    """Main entry point for configuration system."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logger.add(lambda msg: print(msg, end=""), level="DEBUG")
    else:
        logger.add(lambda msg: print(msg, end=""), level="INFO")

    try:
        # Load base configuration
        if not args.config:
            parser.error("--config is required")

        config_data = load_yaml_config(args.config)

        # Apply CLI overrides
        cli_overrides = parse_cli_overrides(args)
        config = create_session_config(config_data, cli_overrides)

        # Additional validation
        validate_configuration(config)

        # Discover trials
        discovered_trials = discover_trials(config)

        if args.validate_config:
            logger.success("Configuration validation complete")
            logger.info(f"Session: {config.name}")
            logger.info(f"Subject: {config.subject_id}")
            logger.info(f"Output: {config.output_directory}")
            logger.info(f"Static trials: {len(discovered_trials['static'])}")
            logger.info(f"Dynamic trials: {len(discovered_trials['dynamic'])}")
            return

        # Run the session pipeline
        session_results = run_session_pipeline(config, discovered_trials)

        # Print session summary
        logger.success("Session Summary:")
        logger.info(f"  Session: {session_results['session_name']}")
        logger.info(f"  Subject: {session_results['subject_id']}")
        logger.info(
            f"  Static trials processed: {len(session_results['static_results'])}"
        )
        logger.info(
            f"  Dynamic trials processed: {len(session_results['dynamic_results'])}"
        )
        if session_results["errors"]:
            logger.warning(f"  Errors encountered: {len(session_results['errors'])}")
            for error in session_results["errors"]:
                logger.warning(f"    - {error}")
        else:
            logger.success("  All trials processed successfully")

    except Exception as e:
        logger.error(f"Configuration failed: {e}")
        raise


def generate_session_documentation_comprehensive(
    config: SessionConfig, session_result: SessionResult, output_dir: str
) -> None:
    """
    Generate comprehensive session documentation for thesis and reproducibility.

    Creates:
    1. Session summary JSON with complete metadata
    2. Parameter tables markdown for thesis Methods section
    3. Trial summaries CSV
    4. README.md with reproducibility instructions
    5. File manifest JSON

    Args:
        config: Session configuration
        session_result: Complete session results
        output_dir: Directory to save documentation files
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Generating session documentation")

    # 1. Session summary JSON
    session_summary = {
        "session_metadata": {
            "name": session_result.session_name,
            "subject_id": session_result.subject_id,
            "created_at": session_result.created_at.isoformat(),
            "output_directory": session_result.output_directory,
        },
        "model_files": {
            "base_model": config.base_model,
            "marker_set": config.marker_set,
            "task_set": config.task_set,
            "actuators": config.actuators,
            "control_constraints": config.control_constraints,
        },
        "subject_parameters": {
            "mass_kg": config.mass,
        },
        "processing_parameters": {
            "lowpass_cutoff_hz": config.lowpass_cutoff,
            "ik_accuracy": config.ik_accuracy,
            "cmc_time_window_s": config.cmc_time_window,
        },
        "force_plate_mapping": config.body_mapping,
        "required_markers": config.required_markers,
        "trial_configurations": {
            "static_trials": [trial.name for trial in config.static_trials],
            "dynamic_trials": [trial.pattern for trial in config.dynamic_trials],
        },
        "scaling_results": {
            "trial_path": session_result.scaling_result.trial_path,
            "limb_lengths": session_result.scaling_result.limb_lengths,
            "time_range": session_result.scaling_result.time_range,
            "created_at": session_result.scaling_result.created_at.isoformat(),
        },
        "dynamic_trial_results": [
            {
                "trial_path": result.trial_path,
                "time_range": result.time_range,
                "created_at": result.created_at.isoformat(),
            }
            for result in session_result.dynamic_trial_results
        ],
        "processing_summary": {
            "total_dynamic_trials": len(session_result.dynamic_trial_results),
            "successful_trials": session_result.success_count,
            "failed_trials": session_result.failure_count,
        },
    }

    summary_path = output_path / "session_summary.json"
    with open(summary_path, "w") as f:
        json.dump(session_summary, f, indent=2)
    logger.success(f"Session summary saved: {summary_path}")

    # 2. Parameter tables markdown for thesis Methods section
    markdown_content = f"""# Rat Hindlimb Biomechanics Analysis Parameters

## Session Information
- **Session Name**: {session_result.session_name}
- **Subject ID**: {session_result.subject_id}
- **Analysis Date**: {session_result.created_at.strftime("%Y-%m-%d")}

## Subject Parameters
| Parameter | Value | Units |
|-----------|-------|-------|
| Mass | {config.mass} | kg |

## Processing Parameters
| Parameter | Value | Units | Description |
|-----------|-------|-------|-------------|
| Low-pass Filter Cutoff | {config.lowpass_cutoff} | Hz | Butterworth filter cutoff frequency |
| IK Accuracy | {config.ik_accuracy} | - | Inverse kinematics convergence tolerance |
| CMC Time Window | {config.cmc_time_window} | s | Computed muscle control integration window |

## Force Plate Mapping
| Force Plate Context | OpenSim Body |
|---------------------|--------------|
"""

    for context, body in config.body_mapping.items():
        markdown_content += f"| {context} | {body} |\n"

    markdown_content += "\n## Scaling Parameters\n"
    markdown_content += "| Trial | Right Femur (mm) | Left Femur (mm) | Right Tibia (mm) | Left Tibia (mm) | Right Foot (mm) | Left Foot (mm) |\n"
    markdown_content += "|-------|------------------|-----------------|------------------|-----------------|-----------------|----------------|\n"

    lengths = session_result.scaling_result.limb_lengths
    trial_name = Path(session_result.scaling_result.trial_path).stem
    markdown_content += f"| {trial_name} | {lengths['right_femur']:.1f} | {lengths['left_femur']:.1f} | {lengths['right_tibia']:.1f} | {lengths['left_tibia']:.1f} | {lengths['right_foot']:.1f} | {lengths['left_foot']:.1f} |\n"

    markdown_content += "\n## Required Markers\n"
    for marker in config.required_markers:
        markdown_content += f"- {marker}\n"

    params_path = output_path / "analysis_parameters.md"
    with open(params_path, "w") as f:
        f.write(markdown_content)
    logger.success(f"Parameter tables saved: {params_path}")

    # 3. Trial summaries CSV
    csv_content = "Trial Name,Trial Path,HDF5 Path,TRC Path,Scaled Model Path,IK Results Path,CMC Results Path,Time Range Start (s),Time Range End (s),Right Femur (mm),Left Femur (mm),Right Tibia (mm),Left Tibia (mm),Right Foot (mm),Left Foot (mm)\n"

    # Scaling trial
    lengths = session_result.scaling_result.limb_lengths
    trial_name = Path(session_result.scaling_result.trial_path).stem
    csv_content += f"{trial_name},{session_result.scaling_result.trial_path},{session_result.scaling_result.hdf5_path},{session_result.scaling_result.trc_path},{session_result.scaling_result.scaled_model_path},,,{session_result.scaling_result.time_range[0]},{session_result.scaling_result.time_range[1]},{lengths['right_femur']:.3f},{lengths['left_femur']:.3f},{lengths['right_tibia']:.3f},{lengths['left_tibia']:.3f},{lengths['right_foot']:.3f},{lengths['left_foot']:.3f}\n"

    # Dynamic trials
    for result in session_result.dynamic_trial_results:
        lengths = session_result.scaling_result.limb_lengths  # Same scaling for all
        trial_name = Path(result.trial_path).stem
        csv_content += f"{trial_name},{result.trial_path},{result.hdf5_path},,{session_result.scaling_result.scaled_model_path},{result.ik_result_path},{result.cmc_result_path},{result.time_range[0]},{result.time_range[1]},{lengths['right_femur']:.3f},{lengths['left_femur']:.3f},{lengths['right_tibia']:.3f},{lengths['left_tibia']:.3f},{lengths['right_foot']:.3f},{lengths['left_foot']:.3f}\n"

    csv_path = output_path / "trial_summaries.csv"
    with open(csv_path, "w") as f:
        f.write(csv_content)
    logger.success(f"Trial summaries CSV saved: {csv_path}")

    # 4. README.md with reproducibility instructions
    readme_content = f"""# Rat Hindlimb Session Analysis: {session_result.session_name}

## Overview
This directory contains the complete analysis pipeline and results for rat hindlimb biomechanics analysis.

**Session**: {session_result.session_name}
**Subject**: {session_result.subject_id}
**Generated**: {session_result.created_at.strftime("%Y-%m-%d %H:%M:%S")}

## Reproducibility Instructions

### Prerequisites
- Python 3.12+
- OpenSim 4.x
- RatHindlimb package
- MoveDB Core library

### Setup
1. Install dependencies:
   ```bash
   uv sync
   ```

2. Ensure RatHindlimb package is available in your Python path.

### Running the Analysis
1. Use the configuration file to reproduce this analysis:
   ```bash
   python rat_hindlimb_session_pipeline.py --config path/to/config.yaml
   ```

2. For validation only:
   ```bash
   python rat_hindlimb_session_pipeline.py --config path/to/config.yaml --validate-config
   ```

### Key Parameters
- **Subject Mass**: {config.mass} kg
- **Low-pass Cutoff**: {config.lowpass_cutoff} Hz
- **IK Accuracy**: {config.ik_accuracy}
- **CMC Time Window**: {config.cmc_time_window} s

### File Structure
- `session_summary.json`: Complete session metadata
- `analysis_parameters.md`: Parameter tables for thesis Methods section
- `trial_summaries.csv`: Summary of all processed trials
- `file_manifest.json`: Complete list of all generated files
- `results/`: Directory containing all analysis outputs

### Scaling Results
Scaling performed on static trial with calculated limb lengths.

### Dynamic Trial Results
Processed {session_result.success_count} dynamic trials successfully, {session_result.failure_count} failed.

## Contact
Generated by MoveDB Core v1.0
"""

    readme_path = output_path / "README.md"
    with open(readme_path, "w") as f:
        f.write(readme_content)
    logger.success(f"README.md saved: {readme_path}")

    # 5. File manifest JSON
    file_manifest = {
        "session": session_result.session_name,
        "subject": session_result.subject_id,
        "generated_at": session_result.created_at.isoformat(),
        "files": {
            "documentation": [
                str(summary_path),
                str(params_path),
                str(csv_path),
                str(readme_path),
            ],
            "scaling_outputs": [
                session_result.scaling_result.hdf5_path,
                session_result.scaling_result.trc_path,
                session_result.scaling_result.scaled_model_path,
                session_result.scaling_result.scaling_params_path,
                session_result.scaling_result.provenance_path,
            ],
            "dynamic_trial_outputs": [
                {
                    "trial": Path(result.trial_path).stem,
                    "files": [
                        result.hdf5_path,
                        result.ik_result_path,
                        result.cmc_result_path,
                    ],
                }
                for result in session_result.dynamic_trial_results
            ],
        },
        "total_files": 4
        + 5
        + len(session_result.dynamic_trial_results)
        * 3,  # docs + scaling + dynamic files per trial
    }

    manifest_path = output_path / "file_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(file_manifest, f, indent=2)
    logger.success(f"File manifest saved: {manifest_path}")

    logger.success("Session documentation generation complete")


if __name__ == "__main__":
    main()

