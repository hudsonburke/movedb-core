#!/usr/bin/env python3
"""Test the improved find_full_frames functionality"""

import numpy as np

def test_full_frames_logic():
    """Test the logic for finding full frames using gap detection"""
    
    # Simulate the improved algorithm
    first_frame = 100
    last_frame = 110
    
    # All possible frames
    all_frames = set(range(first_frame, last_frame + 1))
    print(f"All frames: {sorted(all_frames)}")
    
    # Simulate gaps from different markers
    marker_gaps = {
        "marker1": [(102, 104), (108, 109)],  # gaps at 102-104 and 108-109
        "marker2": [(105, 106)],              # gap at 105-106
        "marker3": []                         # no gaps
    }
    
    print(f"Marker gaps: {marker_gaps}")
    
    # Remove all frames that have gaps in any marker
    full_frames = all_frames.copy()
    for marker, gaps in marker_gaps.items():
        for gap_start, gap_end in gaps:
            gap_frames = set(range(gap_start, gap_end + 1))
            full_frames -= gap_frames
            print(f"After removing {marker} gaps {gap_frames}: {sorted(full_frames)}")
    
    print(f"Final full frames: {sorted(full_frames)}")
    print(f"Expected full frames: [100, 101, 107, 110]")
    
    # Test edge cases
    print("\n=== Edge Cases ===")
    
    # All frames have gaps
    all_gaps = {"marker1": [(100, 110)]}
    full_frames_none = all_frames.copy()
    for marker, gaps in all_gaps.items():
        for gap_start, gap_end in gaps:
            gap_frames = set(range(gap_start, gap_end + 1))
            full_frames_none -= gap_frames
    print(f"All gaps case: {sorted(full_frames_none)}")
    
    # No gaps
    no_gaps = {"marker1": []}
    full_frames_all = all_frames.copy()
    for marker, gaps in no_gaps.items():
        for gap_start, gap_end in gaps:
            gap_frames = set(range(gap_start, gap_end + 1))
            full_frames_all -= gap_frames
    print(f"No gaps case: {sorted(full_frames_all)}")

if __name__ == "__main__":
    test_full_frames_logic()
