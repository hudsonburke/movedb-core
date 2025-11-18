import os
from pyopensim.tools import InverseKinematicsTool, IKTaskSet
from pyopensim.simulation import Model 
import numpy as np
from .abstract_tool import AbstractToolSettings

class IKSettings(AbstractToolSettings):
    
    marker_file: str
    coordinate_file: str
    output_motion_file: str
    start_time: float = -1.0
    end_time: float = -1.0
    task_set: IKTaskSet | None = None
    constraint_weight: float = 1.0
    accuracy: float = 1e-5
    report_marker_locations: bool = False

    @classmethod
    def from_setup_file(cls, filepath: str):
        pass
    
    def create_tool(self) -> InverseKinematicsTool:
        return InverseKinematicsTool()
    

def run_ik_tool(
    name: str,
    model_path: str,
    trc_path: str | None = None,
    output_dir: str = ".",
    start_time: float = 0.0, # TODO: Make -1 and read start + end from trc file
    end_time: float = np.inf, # TODO: Maybe an unnecessary import
    ik_setup_path: str | None = None,
) -> tuple[str, str]:
    """
    Run OpenSim Inverse Kinematics analysis.
    Parameters
    ----------
    name : str
        Name for the analysis, used in output file names.
    model_path : str
        Path to the OpenSim model file (.. Must be compatible with the marker set in the TRC file.
    trc_path : str | None, optional
        Path to the TRC file containing marker data. If None, assumes a TRC file named
        {name}.trc in the output directory, by default None
    output_dir : str, optional
        Directory to save output files, by default "."
    start_time : float, optional
        Start time for the analysis, by default 0.0
    end_time : float, optional
        End time for the analysis, by default np.inf (use end of TRC file)
    ik_setup_path : str | None, optional
        Path to the Inverse Kinematics setup file (.xml). If None, a default setup is used, by default None
    Returns
    -------
    ik_results_path : str
        Path to the Inverse Kinematics results file (.mot).
    ik_setup_path : str
        Path to the Inverse Kinematics setup file (.xml).
    """
    if ik_setup_path is None:
        ik_tool = InverseKinematicsTool()
    else:
        ik_tool = InverseKinematicsTool(os.path.abspath(ik_setup_path))

    ik_tool.setName(name)
    model = Model(os.path.abspath(model_path))
    ik_tool.setModel(model)
    ik_tool.setMarkerDataFileName(f"{name}.trc" if not trc_path else trc_path)
    ik_results_name = f"{name}_ik.mot"
    ik_results_path = os.path.join(output_dir, ik_results_name)
    ik_tool.setOutputMotionFileName(ik_results_path)
    ik_tool.setResultsDir(os.path.abspath(output_dir))

    # TODO: Could be pulled from trc
    ik_tool.setStartTime(start_time)
    ik_tool.setEndTime(end_time)

    out_ik_setup_path = os.path.join(output_dir, f"{name}_ik_setup.xml")
    ik_tool.printToXML(out_ik_setup_path)
    ik_tool.run()
    return ik_results_path, out_ik_setup_path

