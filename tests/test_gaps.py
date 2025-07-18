#!/usr/bin/env python3
"""Test the simplified gap detection logic"""

import numpy as np

def test_gap_detection():
    """Test various gap patterns"""
    
    def find_gaps(missing_mask, first_frame=0):
        """Simplified gap detection logic"""
        gaps = []
        if np.any(missing_mask):
            # Add padding to handle edge cases
            padded_mask = np.concatenate(([False], missing_mask, [False]))
            
            # Find transitions: False->True (gap starts) and True->False (gap ends)
            diff = np.diff(padded_mask.astype(int))
            gap_starts = np.where(diff == 1)[0]  # Transitions from 0 to 1
            gap_ends = np.where(diff == -1)[0] - 1  # Transitions from 1 to 0, adjust by -1
            
            # Convert to absolute frames
            for gap_start, gap_end in zip(gap_starts, gap_ends):
                gaps.append((gap_start + first_frame, gap_end + first_frame))
        return gaps
    
    # Test case 1: Single gap in the middle
    mask1 = np.array([False, False, True, True, True, False, False])
    gaps1 = find_gaps(mask1)
    print(f"Test 1 - Single gap: {gaps1}")
    print(f"Expected: [(2, 4)]")
    
    # Test case 2: Multiple gaps
    mask2 = np.array([False, True, True, False, False, True, False, True, True, True])
    gaps2 = find_gaps(mask2)
    print(f"\nTest 2 - Multiple gaps: {gaps2}")
    print(f"Expected: [(1, 2), (5, 5), (7, 9)]")
    
    # Test case 3: Gap at the beginning
    mask3 = np.array([True, True, False, False, True, False])
    gaps3 = find_gaps(mask3)
    print(f"\nTest 3 - Gap at start: {gaps3}")
    print(f"Expected: [(0, 1), (4, 4)]")
    
    # Test case 4: Gap at the end
    mask4 = np.array([False, False, True, False, True, True])
    gaps4 = find_gaps(mask4)
    print(f"\nTest 4 - Gap at end: {gaps4}")
    print(f"Expected: [(2, 2), (4, 5)]")
    
    # Test case 5: No gaps
    mask5 = np.array([False, False, False, False])
    gaps5 = find_gaps(mask5)
    print(f"\nTest 5 - No gaps: {gaps5}")
    print(f"Expected: []")
    
    # Test case 6: All gaps
    mask6 = np.array([True, True, True, True])
    gaps6 = find_gaps(mask6)
    print(f"\nTest 6 - All gaps: {gaps6}")
    print(f"Expected: [(0, 3)]")
    
    # Test with offset first_frame
    mask7 = np.array([False, True, True, False])
    gaps7 = find_gaps(mask7, first_frame=100)
    print(f"\nTest 7 - With offset: {gaps7}")
    print(f"Expected: [(101, 102)]")

if __name__ == "__main__":
    test_gap_detection()
