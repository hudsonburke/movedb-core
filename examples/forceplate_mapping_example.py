"""
Example: Using Forceplate-to-Body Mapping Utilities

This example demonstrates how to use the standalone utility functions
for determining which forceplates contact which bodies, useful when:
- You have forceplate data but not a Trial object
- You want to use alternative contact detection methods (force thresholds, video, etc.)
- You need more control over the external forces configuration
"""

from movedb.osim.utils import (
    get_forceplate_body_mapping_from_enf,
    create_opensim_external_forces
)
from movedb.osim.io.write import export_external_loads

# ===== Method 1: Using ENF File =====

# Parse ENF file to get forceplate-to-body assignments
fp_mapping = get_forceplate_body_mapping_from_enf(
    enf_path="Walk05.Trial.enf",
    body_mapping={'Left': 'foot_l', 'Right': 'foot_r'}
)
# Result: {3: 'foot_r'}  (if ENF has FP3=Right)

# Create external force objects
forceplate_names = ["FP1", "FP2", "FP3"]
external_forces = create_opensim_external_forces(
    forceplate_names=forceplate_names,
    fp_to_body_mapping=fp_mapping,
    force_expressed_in_body="ground",
    point_expressed_in_body="ground"
)

# Export to XML file
export_external_loads(
    filepath="external_loads.xml",
    external_forces=external_forces,
    datafile_name="grf.mot"
)

# ===== Method 2: Manual Contact Detection =====

# If you determine contact some other way (e.g., force threshold analysis)
# you can directly create the mapping:

# Example: Analysis shows FP2 and FP3 both contact right foot during trial
manual_mapping = {
    2: 'foot_r',  # FP2 contacts right foot
    3: 'foot_r',  # FP3 also contacts right foot
}

external_forces = create_opensim_external_forces(
    forceplate_names=["FP1", "FP2", "FP3"],
    fp_to_body_mapping=manual_mapping
)

# Result: 2 ExternalForce objects, both applied to 'foot_r'

# ===== Method 3: Using Different Body Names =====

# If your model uses different body naming conventions
custom_body_mapping = {
    'Left': 'calcn_l',  # Left calcaneus
    'Right': 'calcn_r',  # Right calcaneus
}

fp_mapping = get_forceplate_body_mapping_from_enf(
    enf_path="Walk05.Trial.enf",
    body_mapping=custom_body_mapping
)

external_forces = create_opensim_external_forces(
    forceplate_names=["FP1", "FP2", "FP3"],
    fp_to_body_mapping=fp_mapping
)

print("External forces created with custom body names!")
