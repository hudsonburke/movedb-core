import os
from pyopensim.tools import ScaleTool, ModelScaler, MarkerPlacer, GenericModelMaker
from pyopensim.common import ScaleSet
from pyopensim.common import ArrayDouble
from pyopensim.simbody import Vec3
from typing import Iterable
from pydantic.dataclasses import dataclass

"""
There are three parts to the scale tool:
- GenericModelMaker
    - unscaled_model_path
    - marker_set_path
- ModelScaler
"""

@dataclass
class ScaleSetup:
    name: str
    unscaled_model_path: str
    marker_set_path: str
    marker_file_name: str
    scale_factors: dict[str, Iterable] = {}
    preserve_mass_distribution: bool = True
    subject_mass: float | None = None
    time_start: float | None = None
    time_end: float | None = None

def run_scale_tool(
    name: str,
    unscaled_model_path: str, 
    marker_set_path: str, 
    marker_file_name: str,
    scale_factors: dict[str, Iterable] = {},
    subject_mass: float | None = None,
    scale_setup_path: str | None = None,
    time_start: float | None = None,
    time_end: float | None = None,
    ):
    # From OpenSim API documentation: All files in workflow are specified relative to where the subject file is
    if scale_setup_path is not None and os.path.exists(scale_setup_path):
        scale_tool = ScaleTool(os.path.abspath(scale_setup_path))
    else:
        scale_tool = ScaleTool()
    scale_tool.setName(name)
    
    model_scaler: ModelScaler = scale_tool.getModelScaler()
    model_scaler.setApply(True)
    model_scaler.setMarkerFileName(marker_file_name)
    
    time_range = ArrayDouble()
    time_range.set(0, time_start)
    time_range.set(1, time_end)
    model_scaler.setTimeRange(time_range)

    if subject_mass is not None:
        model_scaler.setSubjectMass(subject_mass)
        
    scale_set: ScaleSet = model_scaler.getScaleSet()
    for scale_factor, vec in scale_factors.items():
        try:
            vec = Vec3(*vec) if not isinstance(vec, Vec3) else vec
            scale_set.get(scale_factor).setScaleFactors(vec)
        except Exception as e:
            print(f"Warning: Could not set scale factor '{scale_factor}' with value '{vec}': {e}")
            continue
    
    marker_placer: MarkerPlacer = scale_tool.getMarkerPlacer()
    marker_placer.setApply(True)
    marker_placer.setMarkerFileName(marker_file_name)

    generic_model_maker: GenericModelMaker = scale_tool.getGenericModelMaker()
    generic_model_maker.setModelFileName(unscaled_model_path)
    generic_model_maker.setMarkerSetFileName(marker_set_path)
    
    scale_tool.run()
