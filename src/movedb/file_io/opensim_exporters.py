"""OpenSim export functionality."""

import os
from typing import TYPE_CHECKING, Any
from loguru import logger
from pydantic import BaseModel
import polars as pl
import numpy as np

if TYPE_CHECKING:
    import opensim as osim

    OPENSIM_AVAILABLE = True
else:
    try:
        import opensim as osim

        OPENSIM_AVAILABLE = True
    except ImportError:
        OPENSIM_AVAILABLE = False
        osim = None  # type: ignore
        logger.warning(
            "OpenSim not available. OpenSim export features will be disabled.",
            UserWarning,
            stacklevel=2
        )


def get_units_conversion_factor(from_units: str, to_units: str) -> float:
    if not OPENSIM_AVAILABLE:
        raise ImportError("OpenSim is required for unit conversion functionality")
    if from_units == to_units:
        return 1.0
    from_u = osim.Units(from_units)
    to_u = osim.Units(to_units)
    return from_u.convertTo(to_u)

def export_trc(
    filepath: str,
    markers: dict[str, np.ndarray],
    time: np.ndarray,
    rate: float,
    units: str,
    output_units: str | None = None,
    rotation: np.ndarray = np.eye(3),
) -> None:
    """
    Export marker data to TRC file format used by OpenSim
    """
    if not OPENSIM_AVAILABLE:
        raise ImportError("OpenSim is required for export functionality")

    # Markers is expected to be a dict of marker name to Nx3 numpy array of coordinates
    num_frames = len(time)
    if any(len(coords) != num_frames for coords in markers.values()):
        raise ValueError(
            "All markers must have the same number of frames as the time array"
        )
    assert all(
        coords.shape[1] == 3 for coords in markers.values()
    ), "All marker coordinates must be 3D"

    table = osim.TimeSeriesTableVec3()
    marker_names = list(markers.keys())
    table.setColumnLabels(marker_names)
    conversion_factor = 1.0
    if output_units is not None and units != output_units:
        logger.warning(
            f"Output units {output_units} do not match points units {units}. Converting coordinates."
        )
        conversion_factor = get_units_conversion_factor(units, output_units)
    table.addTableMetaDataString(
        "Units", units if output_units is None else output_units
    )
    table.addTableMetaDataString("DataRate", str(rate))
    for frame in range(num_frames):
        row = []
        for marker_name, coords in markers.items():
            in_coords = coords[frame]
            if in_coords is not None:
                coords_rotated = np.array(
                    rotation @ np.array(in_coords).T
                ).T  # Apply rotation if needed
                coords_converted = (
                    coords_rotated * conversion_factor
                )  # Convert coordinates if needed
            else:
                coords_converted = np.array([np.nan, np.nan, np.nan])
            row.append(
                osim.Vec3(coords_converted[0], coords_converted[1], coords_converted[2])
            )
        time_val = time[frame]
        table.appendRow(time_val, osim.RowVectorVec3(row))
    adapter = osim.TRCFileAdapter()
    adapter.write(table, filepath)

def export_mot(
    filepath: str,
    data: pl.DataFrame,
    metadata: dict[str, Any] = {}
    ):
    """
    Export data to OpenSim MOT file format.
    """
    if not OPENSIM_AVAILABLE:
        raise ImportError("OpenSim is required for export functionality")
    mot_table = osim.TimeSeriesTable()
    
    if "time" not in data.columns:
        raise ValueError("Data must contain a 'time' column for MOT export")
    
    for row in data.iter_rows(named=True):
        time_val = row["time"]
        row_data = [row[col] for col in data.columns if col != "time"]
        mot_table.appendRow(time_val, osim.RowVector(row_data))

    column_labels = [col for col in data.columns if col != "time"]
    mot_table.setColumnLabels(column_labels)

    n_rows = len(data)
    metadata_rows = metadata.pop("nRows", None)
    if metadata_rows is not None and str(metadata_rows) != str(n_rows):
        logger.warning(
            f"Metadata 'nRows' does not match data length: {metadata.get('nRows', 'None')} != {n_rows}"
        )
    mot_table.addTableMetaDataString("nRows", str(n_rows))
        
    n_columns = len(data.columns)
    metadata_columns = metadata.pop("nColumns", None)
    if metadata_columns is not None and str(metadata_columns) != str(n_columns):
        logger.warning(
            f"Metadata 'nColumns' does not match data columns: {metadata.get('nColumns', 'None')} != {n_columns}"
        )
    mot_table.addTableMetaDataString("nColumns", str(n_columns))
    
    for key, value in metadata.items():
        mot_table.addTableMetaDataString(key, str(value))
    mot_file = osim.STOFileAdapter()
    mot_file.write(mot_table, filepath)

class OpenSimExternalForce(BaseModel):
    name: str
    applied_to_body: str
    force_expressed_in_body: str = "ground"
    point_expressed_in_body: str = "ground"
    force_identifier: str = r"force_v"
    point_identifier: str = r"force_p"
    torque_identifier: str = r"moment_"
    data_source_name: str | None = None
    
    def to_opensim(self) -> 'osim.ExternalForce':
        """
        Convert to OpenSim ExternalForce object.
        """
        ext_force = osim.ExternalForce()
        ext_force.setName(self.name)
        ext_force.setAppliedToBodyName(self.applied_to_body)
        ext_force.setForceExpressedInBodyName(self.force_expressed_in_body)
        ext_force.setPointExpressedInBodyName(self.point_expressed_in_body)
        ext_force.setForceIdentifier(self.force_identifier)
        ext_force.setPointIdentifier(self.point_identifier)
        ext_force.setTorqueIdentifier(self.torque_identifier)

        if self.data_source_name is not None:
            ext_force.set_data_source_name(self.data_source_name)

        return ext_force

def export_external_loads(
    filepath: str,
    external_forces: list[OpenSimExternalForce],
    datafile_name: str | None = None,
) -> None:
    """
    Export external loads to OpenSim ExternalLoads .xml file.
    """
    if not OPENSIM_AVAILABLE:
        raise ImportError("OpenSim is required for export functionality")

    ext_loads = osim.ExternalLoads()
    for force in external_forces:
        ext_loads.cloneAndAppend(force.to_opensim())
    if datafile_name is not None:
        ext_loads.setDataFileName(datafile_name)
    ext_loads.printToXML(filepath)
    
def export_force_platforms(
        output_dir: str,
        rotation: np.ndarray = np.eye(3),
        mot_filename: str = 'forces.mot',
        unit_force: str = "N",
        unit_position: str = "m",
        unit_moment: str = "Nm",
        metadata: dict[str, Any] = {},
    ) -> None:
    """
    Export force plate metadata to OpenSim ExternalLoads .xml file and the data to a .mot file.
    """
    if not OPENSIM_AVAILABLE:
        raise ImportError("OpenSim is required for export functionality")
    
    ext_loads = osim.ExternalLoads()

def opensim_ik(
    name: str,
    model_path: str,
    trc_path: str | None = None,
    output_dir: str = ".",
    start_time: float = 0.0,
    end_time: float = np.inf,
    ik_setup_path: str | None = None,
) -> tuple[str, str]:
    """
    Run OpenSim Inverse Kinematics analysis.
    Parameters
    ----------
    name : str
        Name for the analysis, used in output file names.
    model_path : str
        Path to the OpenSim model file (.osim). Must be compatible with the marker set in the TRC file.
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
        ik_tool = osim.InverseKinematicsTool()
    else:
        ik_tool = osim.InverseKinematicsTool(os.path.abspath(ik_setup_path))

    ik_tool.setName(name)
    model = osim.Model(os.path.abspath(model_path))
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

def opensim_id(
    name: str,
    model_path: str,
    ik_path: str,
    output_dir: str = ".",
    id_setup_path: str | None = None,
    filter_cutoff: float = -1.0,  # Hz - Default is no filtering
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
