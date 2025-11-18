"""OpenSim export functionality."""
import os
from typing import Any, TYPE_CHECKING
from loguru import logger
from pydantic import BaseModel
import polars as pl
import numpy as np
from pyopensim.common import TimeSeriesTable, TimeSeriesTableVec3, STOFileAdapter, TRCFileAdapter
from pyopensim.simulation import ExternalForce, ExternalLoads
from pyopensim.simbody import Vec3, RowVector, RowVectorVec3
from .utils import get_unit_conversion

if TYPE_CHECKING:
    from ..models import Trial

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
    # Markers is expected to be a dict of marker name to Nx3 numpy array of coordinates
    num_frames = len(time)
    if any(len(coords) != num_frames for coords in markers.values()):
        raise ValueError(
            "All markers must have the same number of frames as the time array"
        )
    assert all(
        coords.shape[1] == 3 for coords in markers.values()
    ), "All marker coordinates must be 3D"

    table = TimeSeriesTableVec3()
    marker_names = list(markers.keys())
    table.setColumnLabels(marker_names)
    conversion_factor = 1.0
    if output_units is not None and units != output_units:
        logger.warning(
            f"Output units {output_units} do not match points units {units}. Converting coordinates."
        )
        conversion_factor = get_unit_conversion(units, output_units)
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
                Vec3(coords_converted[0], coords_converted[1], coords_converted[2])
            )
        time_val = time[frame]
        table.appendRow(time_val, RowVectorVec3(row))
    adapter = TRCFileAdapter()
    adapter.write(table, filepath)

def export_trial_to_trc(
    trial: "Trial",
    filepath: str,
    output_units: str | None = None,
    rotation: np.ndarray = np.eye(3),
) -> None:
    """
    Export Trial marker data directly to TRC file format.
    
    Reads marker data from HDF5 storage and exports to OpenSim TRC format.
    
    Args:
        trial: Trial model with HDF5 path reference
        filepath: Output TRC file path
        output_units: Optional output units (will convert if different from source)
        rotation: Optional rotation matrix to apply to coordinates
    """
    if trial.hdf5_path is None:
        raise ValueError("Trial has no HDF5 data path")
    
    # Load markers from HDF5
    marker_data_dict = trial.load_markers()
    
    # Extract data
    markers_array = marker_data_dict['data']  # Shape: (n_frames, n_markers, 3)
    marker_names = marker_data_dict['marker_names']
    rate = marker_data_dict['rate']
    units = marker_data_dict['units']
    
    # Convert to dict format expected by export_trc
    markers = {}
    for i, name in enumerate(marker_names):
        # Extract marker data: (n_frames, 3)
        marker_xyz = markers_array[:, i, :]
        # Replace sentinel values with None/NaN
        marker_xyz = np.where(marker_xyz == -9999.0, np.nan, marker_xyz)
        markers[name] = marker_xyz
    
    # Generate time array
    n_frames = markers_array.shape[0]
    time = np.arange(n_frames) / rate
    
    # Export using existing function
    export_trc(
        filepath=filepath,
        markers=markers,
        time=time,
        rate=rate,
        units=units,
        output_units=output_units,
        rotation=rotation
    )
    
    logger.info(f"Exported {len(markers)} markers to {filepath}")

def export_mot(
    filepath: str,
    data: pl.DataFrame,
    metadata: dict[str, Any] = {},
    nans_as_zero: bool = True,
    ):
    """
    Export data to OpenSim MOT file format.
    """
    mot_table = TimeSeriesTable()
    
    if "time" not in data.columns:
        raise ValueError("Data must contain a 'time' column for MOT export")
    
    if nans_as_zero:
        # Replace NaNs with zeros in the data
        data = data.with_columns(
            [pl.col(col).fill_nan(0.0) for col in data.columns if col != "time"]
        )
    
    for row in data.iter_rows(named=True):
        time_val = row["time"]
        row_data = [row[col] for col in data.columns if col != "time"]
        mot_table.appendRow(time_val, RowVector(row_data))

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
    mot_file = STOFileAdapter()
    mot_file.write(mot_table, filepath)

def export_trial_forceplates_to_mot(
    trial: "Trial",
    filepath: str,
    metadata: dict[str, Any] = {},
    rotation: np.ndarray = np.eye(3),
) -> None:
    """
    Export Trial force plate data to MOT file format.
    
    Reads force plate data from HDF5 storage and exports to OpenSim MOT format.
    
    Args:
        trial: Trial model with HDF5 path reference
        filepath: Output MOT file path
        metadata: Optional metadata to include in MOT file
        rotation: Optional rotation matrix to apply to force/moment/cop vectors
    """
    if trial.hdf5_path is None:
        raise ValueError("Trial has no HDF5 data path")
    
    if not trial.forceplate_names:
        raise ValueError("Trial has no force plates")
    
    # Load all force plates
    all_fp_data = trial.load_all_forceplates()
    
    # Build polars DataFrame with all force plate data
    # Each force plate contributes: force_x, force_y, force_z, moment_x, moment_y, moment_z, 
    #                               cop_x, cop_y, cop_z (9 columns per plate)
    
    # Get first force plate to determine number of frames
    first_fp = all_fp_data[trial.forceplate_names[0]]
    n_frames = first_fp['forces'].shape[0]
    rate = first_fp['rate']
    
    # Generate time column
    time = np.arange(n_frames) / rate
    
    # Build data dict
    data_dict = {"time": time}
    
    for fp_name in trial.forceplate_names:
        fp_data = all_fp_data[fp_name]
        forces = fp_data['forces']  # (n_frames, 3)
        moments = fp_data['moments']  # (n_frames, 3)
        cop = fp_data['cop']  # (n_frames, 3)
        
        # Apply rotation if provided
        if not np.allclose(rotation, np.eye(3)):
            forces = (rotation @ forces.T).T
            moments = (rotation @ moments.T).T
            cop = (rotation @ cop.T).T
        
        # Add to data dict with force plate prefix
        prefix = fp_name.replace(" ", "_")
        data_dict[f"{prefix}_force_vx"] = forces[:, 0]
        data_dict[f"{prefix}_force_vy"] = forces[:, 1]
        data_dict[f"{prefix}_force_vz"] = forces[:, 2]
        data_dict[f"{prefix}_moment_x"] = moments[:, 0]
        data_dict[f"{prefix}_moment_y"] = moments[:, 1]
        data_dict[f"{prefix}_moment_z"] = moments[:, 2]
        data_dict[f"{prefix}_force_px"] = cop[:, 0]
        data_dict[f"{prefix}_force_py"] = cop[:, 1]
        data_dict[f"{prefix}_force_pz"] = cop[:, 2]
    
    # Create polars DataFrame
    df = pl.DataFrame(data_dict)
    
    # Export using existing function
    export_mot(filepath=filepath, data=df, metadata=metadata, nans_as_zero=True)
    
    logger.info(f"Exported {len(trial.forceplate_names)} force plates to {filepath}")

class OpenSimExternalForce(BaseModel):
    name: str
    applied_to_body: str
    force_expressed_in_body: str = "ground"
    point_expressed_in_body: str = "ground"
    force_identifier: str = r"force_v"
    point_identifier: str = r"force_p"
    torque_identifier: str = r"moment_"
    data_source_name: str | None = None

    def to_opensim(self) -> ExternalForce:
        """
        Convert to OpenSim ExternalForce object.
        """
        ext_force = ExternalForce()
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
    ext_loads = ExternalLoads()
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
    
    ext_loads = ExternalLoads()

