#!/usr/bin/env python3
"""Simple test to verify gap checking fixes."""
import polars as pl
from movedb.core.time_series import Points, MarkerTrajectory, Analogs, MarkerSchema
from movedb.core.trial import Trial
from pandera.typing.polars import DataFrame

def test_gap_checking():
    print("Testing gap checking fixes...")
    
    # Create test data with known gaps
    n_frames = 10
    first_frame = 5
    last_frame = first_frame + n_frames - 1
    
    # Marker 1: gap at frames 7-9 (indices 2-4)
    marker1_data = pl.DataFrame({
        "x": [1.0, 1.0, None, None, None, 1.0, 1.0, 1.0, 1.0, 1.0],
        "y": [2.0, 2.0, None, None, None, 2.0, 2.0, 2.0, 2.0, 2.0],
        "z": [3.0, 3.0, None, None, None, 3.0, 3.0, 3.0, 3.0, 3.0],
        "residual": [0.1] * n_frames
    })
    
    # Marker 2: gap at frames 11-12 (indices 6-7)
    marker2_data = pl.DataFrame({
        "x": [1.5, 1.5, 1.5, 1.5, 1.5, 1.5, None, None, 1.5, 1.5],
        "y": [2.5, 2.5, 2.5, 2.5, 2.5, 2.5, None, None, 2.5, 2.5],
        "z": [3.5, 3.5, 3.5, 3.5, 3.5, 3.5, None, None, 3.5, 3.5],
        "residual": [0.1] * n_frames
    })
    
    # Marker 3: no gaps
    marker3_data = pl.DataFrame({
        "x": [2.0] * n_frames,
        "y": [3.0] * n_frames,
        "z": [4.0] * n_frames,
        "residual": [0.1] * n_frames
    })
    
    points = Points(
        first_frame=first_frame,
        last_frame=last_frame,
        rate=100.0,
        units="mm",
        trajectories={
            "MARKER1": MarkerTrajectory(data=DataFrame[MarkerSchema](marker1_data), description="Marker 1"),
            "MARKER2": MarkerTrajectory(data=DataFrame[MarkerSchema](marker2_data), description="Marker 2"),
            "MARKER3": MarkerTrajectory(data=DataFrame[MarkerSchema](marker3_data), description="Marker 3")
        }
    )
    
    analogs = Analogs(
        first_frame=first_frame,
        last_frame=last_frame,
        rate=100.0,
        channels={}
    )
    
    trial = Trial(
        name="test_trial",
        points=points,
        analogs=analogs,
        point_gaps={}
    )
    
    print(f"Trial frames: {trial.points.first_frame} to {trial.points.last_frame}")
    print("Expected gaps:")
    print("  MARKER1: frames 7-9")
    print("  MARKER2: frames 11-12")
    print("  MARKER3: no gaps")
    
    # Test gap checking
    gaps = trial.check_point_gaps()
    print("\nActual gaps found:")
    for marker, gap_list in gaps.items():
        print(f"  {marker}: {gap_list}")
    
    # Test find_full_frames
    full_frames = trial.find_full_frames()
    print(f"\nFull frames (all markers have data): {full_frames}")
    
    # Test with specific region
    print("\nTesting region [6, 10]:")
    region_gaps = trial.check_point_gaps(regions=[(6, 10)])
    for marker, gap_list in region_gaps.items():
        print(f"  {marker}: {gap_list}")

if __name__ == "__main__":
    test_gap_checking()
