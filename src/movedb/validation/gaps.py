from ..core import TrialData
from datetime import timedelta
import polars as pl
from pydantic.dataclasses import dataclass
from pydantic import model_validator, Field


@dataclass
class GapInfo:
    start_time: timedelta
    end_time: timedelta

    @property
    def duration(self) -> timedelta:
        return self.end_time - self.start_time

    @model_validator(mode="after")
    def check_duration(self):
        if self.duration.total_seconds() < 0:
            raise ValueError("end_time must be after start_time")
        return self


@dataclass
class MarkerGapResult:
    """Result of gap detection for a single marker."""

    marker_name: str
    duration: timedelta = timedelta(0)
    gaps: list[GapInfo] = Field(default_factory=list)

    @property
    def total_gap_duration(self) -> timedelta:
        return sum((gap.duration for gap in self.gaps), timedelta(0))

    @property
    def gap_percentage(self) -> float:
        """Return percentage of time that is gaps."""
        if self.duration.total_seconds() == 0:
            return 0.0
        return (
            self.total_gap_duration.total_seconds() / self.duration.total_seconds()
        ) * 100

    @property
    def has_gaps(self) -> bool:
        """Return True if the marker has any gaps."""
        return len(self.gaps) > 0


@dataclass
class TrialGapResult:
    """Result of gap detection for an entire trial."""

    trial_name: str
    marker_results: list[MarkerGapResult]

    @property
    def markers_with_gaps(self) -> list[MarkerGapResult]:
        """Return list of markers that have gaps."""
        return [result for result in self.marker_results if result.has_gaps]

    @property
    def total_markers(self) -> int:
        """Return total number of markers checked."""
        return len(self.marker_results)

    @property
    def markers_with_gaps_count(self) -> int:
        """Return number of markers with gaps."""
        return len(self.markers_with_gaps)

    def get_marker_result(self, marker_name: str) -> MarkerGapResult | None:
        """Get gap result for a specific marker."""
        for result in self.marker_results:
            if result.marker_name == marker_name:
                return result
        return None


def detect_marker_gaps(marker: Marker) -> MarkerGapResult:
    """
    Detect gaps in a single marker's data.

    A gap is defined as consecutive frames where any of the x, y, or z coordinates are NaN.

    Args:
        marker: The marker to check for gaps

    Returns:
        MarkerGapResult: Summary of gaps found in the marker
    """
    if not marker.data:
        # No data points means 100% gap
        return MarkerGapResult(
            marker_name=marker.name,
        )

    # Convert to polars DataFrame for efficient processing
    df = marker.to_polars

    if df.is_empty():
        return MarkerGapResult(
            marker_name=marker.name,
        )

    # Identify gaps: rows where x, y, or z are NaN
    df = df.with_columns(
        [
            pl.col("x").is_nan().alias("x_is_nan"),
            pl.col("y").is_nan().alias("y_is_nan"),
            pl.col("z").is_nan().alias("z_is_nan"),
        ]
    )

    # A gap exists when any of three coordinates are NaN
    df = df.with_columns(
        (pl.col("x_is_nan") | pl.col("y_is_nan") | pl.col("z_is_nan")).alias("is_gap")
    )

    # Find gap segments
    gaps = _find_gap_segments(df)

    # Calculate total duration and percentage
    total_duration = df.select(
        pl.col("timestamp").max() - pl.col("timestamp").min()
    ).item()
    if total_duration is None:
        total_duration = timedelta(0)

    return MarkerGapResult(marker_name=marker.name, gaps=gaps, duration=total_duration)


def detect_trial_gaps(trial: Trial) -> TrialGapResult:
    """
    Detect gaps in all markers of a trial.

    Args:
        trial: The trial to check for gaps

    Returns:
        TrialGapResult: Summary of gaps found across all markers in the trial
    """
    marker_results = []

    for marker in trial.markers:
        result = detect_marker_gaps(marker)
        marker_results.append(result)

    return TrialGapResult(trial_name=trial.name, marker_results=marker_results)


def _find_gap_segments(df: pl.DataFrame) -> list[GapInfo]:
    """
    Find continuous segments of gaps in marker data.

    Args:
        df: DataFrame with 'timestamp' and 'is_gap' columns

    Returns:
        List of GapInfo objects representing continuous gap segments
    """
    if df.is_empty():
        return []

    gaps = []

    # Get gap status as a list for easier processing
    gap_data = df.select(["timestamp", "is_gap"]).to_dicts()

    in_gap = False
    gap_start = None

    for row in gap_data:
        timestamp = row["timestamp"]
        is_gap = row["is_gap"]

        if is_gap and not in_gap:
            # Start of a new gap
            in_gap = True
            gap_start = timestamp
        elif not is_gap and in_gap:
            # End of current gap
            in_gap = False
            if gap_start is not None:
                # Gap ended at the previous timestamp, not the current one
                prev_index = gap_data.index(row) - 1
                if prev_index >= 0:
                    gap_end = gap_data[prev_index]["timestamp"]
                else:
                    gap_end = gap_start  # Edge case: single point gap
                gaps.append(GapInfo(gap_start, gap_end))

    # Handle case where data ends while in a gap
    if in_gap and gap_start is not None:
        # Use the last timestamp as gap end
        last_timestamp = gap_data[-1]["timestamp"]
        gaps.append(GapInfo(gap_start, last_timestamp))

    return gaps


def find_markers_with_gaps(trial: Trial, min_gap_percentage: float = 0.0) -> list[str]:
    """
    Find markers with gaps above a specified threshold.

    Args:
        trial: The trial to check
        min_gap_percentage: Minimum gap percentage to include (0-100)

    Returns:
        List of marker names that have gaps above the threshold
    """
    result = detect_trial_gaps(trial)

    return [
        marker_result.marker_name
        for marker_result in result.marker_results
        if marker_result.gap_percentage >= min_gap_percentage
    ]
