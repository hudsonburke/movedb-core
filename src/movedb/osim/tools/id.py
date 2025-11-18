from pyopensim.tools import InverseDynamicsTool
from pyopensim.common import Storage, ArrayStr
from datetime import datetime
from pydantic import Field
from .abstract_tool import AbstractToolSettings
from .results import IDResult


class IDSettings(AbstractToolSettings):
    """Inverse Dynamics tool settings.
    
    Configure and run inverse dynamics analysis to compute generalized forces
    from joint kinematics and external forces.
    """
    
    # ID-specific parameters
    coordinates_file: str = Field(description="Path to coordinates file (.mot) from IK")
    output_forces_file: str = Field(description="Path for output forces file (.sto)")
    lowpass_cutoff_frequency: float = Field(
        -1.0, 
        description="Cutoff frequency for filtering coordinates (-1 = no filtering)"
    )
    excluded_forces: list[str] = Field(
        default_factory=list, 
        description="List of force names to exclude from analysis"
    )
    
    def _create_tool_instance(self) -> InverseDynamicsTool:
        """Create an InverseDynamicsTool instance."""
        return InverseDynamicsTool()
    
    def _configure_tool_specific_settings(self, tool: InverseDynamicsTool) -> None:
        """Configure ID-specific settings.
        
        Parameters
        ----------
        tool : InverseDynamicsTool
            The ID tool instance to configure
        """
        tool.setCoordinatesFileName(self.coordinates_file)
        tool.setOutputGenForceFileName(self.output_forces_file)
        
        if self.lowpass_cutoff_frequency > 0:
            tool.setLowpassCutoffFrequency(self.lowpass_cutoff_frequency)
        
        if self.excluded_forces:
            exclude = ArrayStr()
            for force in self.excluded_forces:
                exclude.append(force)
            tool.setExcludedForces(exclude)
        
        # Auto-detect time range from coordinates file
        if self.initial_time == -1.0 or self.final_time == -1.0:
            sto = Storage(self.coordinates_file)
            if self.initial_time == -1.0:
                tool.setStartTime(sto.getFirstTime())
            if self.final_time == -1.0:
                tool.setEndTime(sto.getLastTime())
    
    def _create_result(
        self,
        setup_file: str,
        success: bool,
        start_time: datetime,
        end_time: datetime,
        warnings: list[str],
        errors: list[str],
    ) -> IDResult:
        """Create an IDResult object.
        
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
        IDResult
            ID-specific result object
        """
        return IDResult(
            success=success,
            setup_file=setup_file,
            results_directory=self.results_directory,
            start_time=start_time,
            end_time=end_time,
            run_time=(end_time - start_time).total_seconds(),
            warnings=warnings,
            errors=errors,
            output_forces_file=self.output_forces_file,
            coordinates_file=self.coordinates_file,
            external_loads_file=self.external_loads_file if self.external_loads_file else None,
        )
    
    def run(self) -> IDResult:
        """Execute ID analysis and return results.
        
        Returns
        -------
        IDResult
            Structured ID results with forces file path and metadata
        """
        return super().run()  # type: ignore[return-value]
