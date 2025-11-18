"""Result classes for OpenSim tool executions."""
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict


class ToolResult(BaseModel):
    """Base class for tool execution results.
    
    Stores metadata about the tool execution and paths to output files.
    Results are lightweight - actual data loading is deferred.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    success: bool = Field(description="Whether the tool completed successfully")
    setup_file: str = Field(description="Path to the tool setup XML file")
    results_directory: str = Field(description="Directory containing output files")
    start_time: datetime = Field(description="When the tool execution started")
    end_time: datetime = Field(description="When the tool execution finished")
    run_time: float = Field(description="Execution time in seconds")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    
    @property
    def output_dir(self) -> Path:
        """Get results directory as Path object."""
        return Path(self.results_directory)
    
    def get_output_file(self, filename: str) -> Path:
        """Get full path to an output file.
        
        Parameters
        ----------
        filename : str
            Name of the output file
            
        Returns
        -------
        Path
            Full path to the output file
        """
        return self.output_dir / filename


class IKResult(ToolResult):
    """Result from Inverse Kinematics analysis.
    
    Attributes
    ----------
    output_motion_file : str
        Path to the output motion (.mot) file containing computed coordinates
    marker_file : str
        Path to the input marker (.trc) file used
    """
    output_motion_file: str = Field(description="Path to output motion file (.mot)")
    marker_file: str = Field(description="Path to input marker file (.trc)")
    
    @property
    def motion_path(self) -> Path:
        """Get path to motion file."""
        return Path(self.output_motion_file)


class IDResult(ToolResult):
    """Result from Inverse Dynamics analysis.
    
    Attributes
    ----------
    output_forces_file : str
        Path to the output forces (.sto) file containing generalized forces
    coordinates_file : str
        Path to the input coordinates (.mot) file used
    """
    output_forces_file: str = Field(description="Path to output forces file (.sto)")
    coordinates_file: str = Field(description="Path to input coordinates file (.mot)")
    external_loads_file: str | None = Field(None, description="Path to external loads file if used")
    
    @property
    def forces_path(self) -> Path:
        """Get path to forces file."""
        return Path(self.output_forces_file)


class CMCResult(ToolResult):
    """Result from Computed Muscle Control analysis.
    
    Attributes
    ----------
    output_controls_file : str
        Path to the output controls file
    output_kinematics_file : str
        Path to the output kinematics file
    desired_kinematics_file : str
        Path to the input desired kinematics file
    """
    output_controls_file: str = Field(description="Path to output controls file")
    output_kinematics_file: str = Field(description="Path to output kinematics file")
    desired_kinematics_file: str = Field(description="Path to input desired kinematics")
    
    @property
    def controls_path(self) -> Path:
        """Get path to controls file."""
        return Path(self.output_controls_file)
    
    @property
    def kinematics_path(self) -> Path:
        """Get path to kinematics file."""
        return Path(self.output_kinematics_file)


class ScaleResult(ToolResult):
    """Result from Scale Tool analysis.
    
    Attributes
    ----------
    output_model_file : str
        Path to the scaled model file
    output_marker_set : str
        Path to the output marker set file
    input_marker_file : str
        Path to the input marker file used for scaling
    """
    output_model_file: str = Field(description="Path to scaled model file")
    output_marker_set: str | None = Field(None, description="Path to output marker set")
    input_marker_file: str = Field(description="Path to input marker file")
    
    @property
    def model_path(self) -> Path:
        """Get path to scaled model."""
        return Path(self.output_model_file)
