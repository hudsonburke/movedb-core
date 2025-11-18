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
    
    def _configure_common_settings(self, tool: InverseDynamicsTool) -> None:
        """ID tool uses different method names than AbstractTool."""
        # ID tool doesn't use standard AbstractTool methods
        tool.setResultsDir(self.results_directory)
        if self.external_loads_file:
            tool.setExternalLoadsFileName(self.external_loads_file)
    
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
            else:
                tool.setStartTime(self.initial_time)
            if self.final_time == -1.0:
                tool.setEndTime(sto.getLastTime())
            else:
                tool.setEndTime(self.final_time)
        else:
            tool.setStartTime(self.initial_time)
            tool.setEndTime(self.final_time)
    
    def save_setup(self, filepath: str | None = None) -> str:
        """Save ID tool setup to XML file with model file path.
        
        Parameters
        ----------
        filepath : str | None
            Path to save the setup file. If None, uses results_directory
            with a default name.
            
        Returns
        -------
        str
            Path to the saved setup file
        """
        tool = self.create_tool()
        
        if filepath is None:
            # Create default setup filename in results directory
            from pathlib import Path
            results_dir = Path(self.results_directory)
            results_dir.mkdir(parents=True, exist_ok=True)
            tool_name = self.__class__.__name__.replace('Settings', '').lower()
            filepath = str(results_dir / f"{tool_name}_setup.xml")
        
        # Write to XML
        tool.printToXML(filepath)
        
        # Read the XML file and add the model_file element
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Insert model_file after the results_directory
        import_line = '\t\t<model_file>{}</model_file>\n'.format(self.model_file)
        
        # Find where to insert - after results_directory if it exists
        results_dir_pos = content.find('</results_directory>')
        if results_dir_pos != -1:
            insert_pos = results_dir_pos + len('</results_directory>') + 1
            content = content[:insert_pos] + import_line + content[insert_pos:]
        else:
            # Otherwise insert after the opening tag
            tag_end = content.find('>', content.find('<InverseDynamicsTool'))
            if tag_end != -1:
                insert_pos = tag_end + 1
                if content[insert_pos] == '\n':
                    insert_pos += 1
                content = content[:insert_pos] + import_line + content[insert_pos:]
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        return filepath
    
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
        """Execute ID analysis using XML-based workflow.
        
        Override the base run() to use XML-first approach: save settings to XML,
        then load tool from XML (which loads the model), then run.
        
        Returns
        -------
        IDResult
            Structured ID results with forces file path and metadata
        """
        from pathlib import Path
        from datetime import datetime
        
        # Ensure results directory exists
        results_dir = Path(self.results_directory)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        warnings = []
        errors = []
        success = False
        start_time = datetime.now()
        
        try:
            # Create and configure tool (for XML generation)
            tool = self.create_tool()
            
            # Save setup XML with model_file injected
            setup_file = self.save_setup()
            
            # CRITICAL: Recreate tool from XML file (this loads the model)
            tool = InverseDynamicsTool(setup_file, True)  # True = load model
            
            # Execute tool
            tool.run()
            success = True
            
        except Exception as e:
            errors.append(str(e))
            setup_file = str(results_dir / "failed_setup.xml")
            raise RuntimeError(f"Tool execution failed: {e}") from e
            
        finally:
            end_time = datetime.now()
            
        return self._create_result(
            setup_file=setup_file,
            success=success,
            start_time=start_time,
            end_time=end_time,
            warnings=warnings,
            errors=errors,
        )
