from pyopensim.tools import InverseKinematicsTool, IKTaskSet
from datetime import datetime
from pydantic import Field
from .abstract_tool import AbstractToolSettings
from .results import IKResult


class IKSettings(AbstractToolSettings):
    """Inverse Kinematics tool settings.
    
    Configure and run inverse kinematics analysis to compute joint angles
    from marker trajectories.
    """
    
    # IK-specific parameters
    marker_file: str = Field(description="Path to marker data file (.trc)")
    output_motion_file: str = Field(description="Path for output motion file (.mot)")
    task_set: IKTaskSet | None = Field(None, description="IK task set for tracking")
    constraint_weight: float = Field(1.0, description="Weight for kinematic constraints")
    accuracy: float = Field(1e-5, description="Convergence accuracy")
    report_marker_locations: bool = Field(False, description="Report marker locations in output")
    
    def _create_tool_instance(self) -> InverseKinematicsTool:
        """Create an InverseKinematicsTool instance."""
        return InverseKinematicsTool()
    
    def _configure_tool_specific_settings(self, tool: InverseKinematicsTool) -> None:
        """Configure IK-specific settings.
        
        Parameters
        ----------
        tool : InverseKinematicsTool
            The IK tool instance to configure
        """
        tool.setMarkerDataFileName(self.marker_file)
        tool.setOutputMotionFileName(self.output_motion_file)
        tool.setConstraintWeight(self.constraint_weight)
        tool.setAccuracy(self.accuracy)
        
        if self.task_set is not None:
            tool.set_IKTaskSet(self.task_set)
    
    def _create_result(
        self,
        setup_file: str,
        success: bool,
        start_time: datetime,
        end_time: datetime,
        warnings: list[str],
        errors: list[str],
    ) -> IKResult:
        """Create an IKResult object.
        
        Parameters
        ----------
        setup_file : str
            Path to the setup XML file
        success : bool
            Whether execution succeeded
        start_time : datetime
            Execution start time
        end_time : datetime
            Execution end time
        warnings : list[str]
            Warning messages
        errors : list[str]
            Error messages
            
        Returns
        -------
        IKResult
            IK-specific result object
        """
        return IKResult(
            success=success,
            setup_file=setup_file,
            results_directory=self.results_directory,
            start_time=start_time,
            end_time=end_time,
            run_time=(end_time - start_time).total_seconds(),
            warnings=warnings,
            errors=errors,
            output_motion_file=self.output_motion_file,
            marker_file=self.marker_file,
        )
    
    def run(self) -> IKResult:
        """Execute IK analysis and return results.
        
        Returns
        -------
        IKResult
            Structured IK results with motion file path and metadata
        """
        return super().run()  # type: ignore[return-value]
