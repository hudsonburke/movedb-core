"""
OpenSim integration module for MoveDB.

This module provides functionality for:
- Reading and writing OpenSim file formats (TRC, MOT, STO)
- Inverse kinematics (IK) analysis
- Inverse dynamics (ID) analysis
- OpenSim model graph analysis and manipulation
- Force platform and external loads export

Note: OpenSim must be installed separately via conda:
    conda install -c conda-forge opensim
"""

from .write import (
    export_trc,
    export_mot,
    export_external_loads,
    export_force_platforms,
    OpenSimExternalForce,
    export_trial_to_trc,
    export_trial_forceplates_to_mot,
)
from .read import sto_to_df, sto_to_numpy
from .osim_graph import OsimGraph
from .utils import get_unit_conversion, createActuatorsFile, createCMCTaskSet
from .cmc import CMCSettings

__all__ = [
    'export_trc',
    'export_mot',
    'export_external_loads',
    'export_force_platforms',
    'OpenSimExternalForce',
    'export_trial_to_trc',
    'export_trial_forceplates_to_mot',
    'sto_to_df',
    'sto_to_numpy',
    'OsimGraph',
    'get_unit_conversion',
    'createActuatorsFile',
    'createCMCTaskSet',
    'CMCSettings',
]

# Version info
__version__ = "0.1.0"