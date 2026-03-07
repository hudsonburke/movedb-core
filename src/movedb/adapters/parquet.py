from .polars import (
    markers_to_polars,
    analogs_to_polars,
    forceplates_to_polars,
    events_to_polars,
)
from ..core import MarkerData, AnalogData, ForceplateData, Event
from pathlib import Path


def write_markers_parquet(
    marker_data: MarkerData,
    path: Path | str,
    trial_name: str | None = None,
) -> Path:
    """
    Write marker data to a Parquet file in wide format.

    Args:
        marker_data: MarkerData instance.
        path: Output file path.
        trial_name: If provided, a 'trial_name' column is included.

    Returns:
        The resolved Path that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = markers_to_polars(marker_data, format="wide", trial_name=trial_name)
    df.write_parquet(path)
    return path


def write_analogs_parquet(
    analog_data: AnalogData,
    path: Path | str,
    trial_name: str | None = None,
) -> Path:
    """
    Write analog data to a Parquet file in wide format.

    Args:
        analog_data: AnalogData instance.
        path: Output file path.
        trial_name: If provided, a 'trial_name' column is included.

    Returns:
        The resolved Path that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = analogs_to_polars(analog_data, format="wide", trial_name=trial_name)
    df.write_parquet(path)
    return path


def write_forceplates_parquet(
    forceplates_data: dict[str, ForceplateData],
    path: Path | str,
    trial_name: str | None = None,
) -> Path:
    """
    Write all force plate data to a single Parquet file in wide format.

    Args:
        forceplates_data: Dict mapping plate name to ForceplateData.
        path: Output file path.
        trial_name: If provided, a 'trial_name' column is included.

    Returns:
        The resolved Path that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = forceplates_to_polars(forceplates_data, format="wide", trial_name=trial_name)
    df.write_parquet(path)
    return path


def write_events_parquet(
    events: list[Event],
    path: Path | str,
    trial_name: str | None = None,
) -> Path:
    """
    Write events to a Parquet file.

    Args:
        events: List of Event instances.
        path: Output file path.
        trial_name: If provided, a 'trial_name' column is included.

    Returns:
        The resolved Path that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = events_to_polars(events, trial_name=trial_name)
    df.write_parquet(path)
    return path
