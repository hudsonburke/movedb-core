import os
import opensim as osim

def opensim_id(
    name: str,
    model_path: str,
    ik_path: str,
    output_dir: str = ".",
    id_setup_path: str | None = None,
    filter_cutoff: float = -1.0, 
    external_loads_file: str | None = None,
    excluded_forces: list[str] | None = None,
) -> tuple[str, str]:
    """
    Run OpenSim Inverse Dynamics analysis.
    
    Parameters
    ----------
    name : str
        Name for the analysis, used in output file names.
    model_path : str
        Path to the OpenSim model file (.osim).
    ik_path : str
        Path to the Inverse Kinematics results file (.mot).
    output_dir : str, optional
        Directory to save output files, by default "."
    id_setup_path : str | None, optional
        Path to the Inverse Dynamics setup file (.xml). If None, a default setup is used, by default None
    filter_cutoff : float, optional
        Cutoff frequency for low-pass filtering the kinematics, by default -1.0 (no filtering)
    external_loads_file : str | None, optional
        Path to the external loads setup file (.xml), by default None
    excluded_forces : list[str] | None, optional
        List of force names to exclude from the analysis, by default None
    
    Returns
    -------
    id_results_path : str
        Path to the Inverse Dynamics results file (.sto).
    id_setup_path : str
        Path to the Inverse Dynamics setup file (.xml).
    """
    # TODO: Maintain relative paths for Setup files
    #   - Set paths relative to the trial directory?
    #   - Could always set working directory to the trial directory
    #   - OR print with relative paths and then set the tool to use absolute paths (see MATLAB toolbox)
    if id_setup_path is None:
        id_tool = osim.InverseDynamicsTool()
    else:
        id_tool = osim.InverseDynamicsTool(os.path.abspath(id_setup_path))

    id_tool.setName(name)
    # model = osim.Model(os.path.abspath(model_path))
    id_tool.setModelFileName(os.path.abspath(model_path))

    ik_sto = osim.Storage(ik_path)
    id_tool.setStartTime(ik_sto.getFirstTime())
    id_tool.setEndTime(ik_sto.getLastTime())
    id_tool.setCoordinatesFileName(ik_path)

    if filter_cutoff > 0:
        id_tool.setLowpassCutoffFrequency(filter_cutoff)

    if external_loads_file is not None:
        # Use the provided external loads file
        id_tool.setExternalLoadsFileName(os.path.abspath(external_loads_file))

    if excluded_forces is not None:
        # Exclude specified forces from the ID analysis
        exclude = osim.ArrayStr()
        for force in excluded_forces:
            exclude.append(force)
        id_tool.setExcludedForces(exclude)

    id_results_name = f"{name}_id.sto"
    id_results_path = os.path.join(output_dir, id_results_name)
    id_tool.setOutputGenForceFileName(id_results_name)
    id_tool.setResultsDir(os.path.abspath(output_dir))
    out_id_setup_path = os.path.join(output_dir, f"{name}_id_setup.xml")
    id_tool.printToXML(out_id_setup_path)
    id_tool.run()

    return id_results_path, out_id_setup_path
