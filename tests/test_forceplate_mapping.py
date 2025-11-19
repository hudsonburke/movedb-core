"""
Test forceplate-to-body mapping utilities.

These tests verify the standalone utility functions for determining which
forceplates contact which bodies, independent of the Trial class.
"""
import pytest
from pathlib import Path

from movedb.osim.utils import (
    get_forceplate_body_mapping_from_enf,
    create_opensim_external_forces
)

# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "data" / "BAA01" / "Baseline"
WALK_ENF = TEST_DATA_DIR / "Walk05.Trial.enf"


class TestForceplateMapping:
    """Test forceplate-to-body mapping utilities."""
    
    def test_parse_enf_file_for_forceplate_mapping(self):
        """Test parsing ENF file to extract forceplate-to-body assignments."""
        assert WALK_ENF.exists(), f"Test ENF file not found: {WALK_ENF}"
        
        # Parse with default mapping
        mapping = get_forceplate_body_mapping_from_enf(
            enf_path=str(WALK_ENF),
            body_mapping={'Left': 'foot_l', 'Right': 'foot_r'}
        )
        
        # Walk05.Trial.enf should have FP3=Right
        assert isinstance(mapping, dict)
        assert 3 in mapping, "Expected FP3 assignment in Walk05 ENF file"
        assert mapping[3] == 'foot_r', "FP3 should map to foot_r (Right foot)"
        
    def test_custom_body_mapping(self):
        """Test using custom body name mappings."""
        # Use different body names
        custom_mapping = {'Left': 'left_foot', 'Right': 'right_foot'}
        
        mapping = get_forceplate_body_mapping_from_enf(
            enf_path=str(WALK_ENF),
            body_mapping=custom_mapping
        )
        
        # Should use the custom body names
        assert 3 in mapping
        assert mapping[3] == 'right_foot'
    
    def test_create_external_forces_from_mapping(self):
        """Test creating OpenSimExternalForce objects from forceplate mapping."""
        # Get forceplate-to-body mapping
        fp_mapping = get_forceplate_body_mapping_from_enf(
            enf_path=str(WALK_ENF),
            body_mapping={'Left': 'foot_l', 'Right': 'foot_r'}
        )
        
        # ENF file has FP3 and FP4, so we need at least 4 forceplates
        forceplate_names = ["ForcePlate_0", "ForcePlate_1", "ForcePlate_2", "ForcePlate_3"]
        external_forces = create_opensim_external_forces(
            forceplate_names=forceplate_names,
            fp_to_body_mapping=fp_mapping
        )
        
        # Verify results - should have forces for the mapped plates
        assert len(external_forces) == len(fp_mapping)
        
        # Check that we got both feet
        body_names = {f.applied_to_body for f in external_forces}
        assert 'foot_r' in body_names  # From FP3=Right
        assert 'foot_l' in body_names  # From FP4=Left
        
        # Check properties of created forces
        for force in external_forces:
            assert force.force_expressed_in_body == "ground"
            assert force.point_expressed_in_body == "ground"
            assert "ForcePlate" in force.name
            assert force.applied_to_body in ['foot_r', 'foot_l']
    
    def test_multiple_forceplates_same_body(self):
        """Test handling multiple forceplates contacting the same body."""
        # Simulate scenario where FP2 and FP3 both contact right foot
        fp_mapping = {2: 'foot_r', 3: 'foot_r'}
        forceplate_names = ["FP1", "FP2", "FP3"]
        
        external_forces = create_opensim_external_forces(
            forceplate_names=forceplate_names,
            fp_to_body_mapping=fp_mapping
        )
        
        # Should create 2 separate force objects
        assert len(external_forces) == 2
        
        # Both should be applied to foot_r
        assert all(f.applied_to_body == 'foot_r' for f in external_forces)
        
        # But have different names and identifiers
        names = [f.name for f in external_forces]
        assert len(set(names)) == 2  # Unique names
        assert "FP2" in names[0] or "FP2" in names[1]
        assert "FP3" in names[0] or "FP3" in names[1]
    
    def test_force_identifiers_match_mot_columns(self):
        """Test that force identifiers match expected MOT file column naming."""
        fp_mapping = {1: 'foot_l'}
        forceplate_names = ["FP1"]
        
        forces = create_opensim_external_forces(
            forceplate_names=forceplate_names,
            fp_to_body_mapping=fp_mapping
        )
        
        force = forces[0]
        
        # Identifiers should match MOT column prefixes
        assert force.force_identifier == "FP1_force_v"
        assert force.point_identifier == "FP1_force_p"
        assert force.torque_identifier == "FP1_moment_"
    
    def test_invalid_forceplate_index(self):
        """Test handling of forceplate indices that don't match available plates."""
        # Mapping references FP5, but only 3 plates exist
        fp_mapping = {5: 'foot_r'}
        forceplate_names = ["FP1", "FP2", "FP3"]
        
        # Should raise error when no valid forces can be created
        with pytest.raises(ValueError, match="No valid external forces"):
            external_forces = create_opensim_external_forces(
                forceplate_names=forceplate_names,
                fp_to_body_mapping=fp_mapping
            )
    
    def test_empty_mapping_raises_error(self):
        """Test that empty forceplate mapping raises an error."""
        fp_mapping = {}
        forceplate_names = ["FP1", "FP2", "FP3"]
        
        with pytest.raises(ValueError, match="No forceplate-to-body mappings provided"):
            create_opensim_external_forces(
                forceplate_names=forceplate_names,
                fp_to_body_mapping=fp_mapping
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
