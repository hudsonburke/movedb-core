from pyopensim.tools import InverseKinematicsTool, IKTaskSet
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from .results import IKResult


class IKSettings(BaseModel):
    """Inverse Kinematics tool settings.
    
    Configure and run inverse kinematics analysis to compute joint angles
    from marker trajectories.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # IK-specific parameters
    model_file: str = Field(description="Name of the .osim file used to construct a model.")
    marker_file: str = Field(description="Path to marker data file (.trc)")
    output_motion_file: str = Field(description="Path for output motion file (.mot)")
    results_directory: str = Field(".", description="Directory used for writing results.")
    task_set: IKTaskSet | None = Field(None, description="IK task set for tracking")
    constraint_weight: float = Field(1.0, description="Weight for kinematic constraints")
    accuracy: float = Field(1e-5, description="Convergence accuracy")
    report_marker_locations: bool = Field(False, description="Report marker locations in output")
    
    def create_tool(self) -> InverseKinematicsTool:
        """Create and configure an InverseKinematicsTool instance.
        
        Returns
        -------
        InverseKinematicsTool
            Configured InverseKinematicsTool instance
        """
        tool = InverseKinematicsTool()
        tool.setResultsDir(self.results_directory)
        tool.setMarkerDataFileName(self.marker_file)
        tool.setOutputMotionFileName(self.output_motion_file)
        
        if self.task_set is not None:
            tool.set_IKTaskSet(self.task_set)
        
        return tool
    
    def save_setup(self, filepath: str | None = None) -> str:
        """Save IK tool setup to XML file with model file path.
        
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
        
        # Write to XML, then add model file manually
        tool.printToXML(filepath)
        
        # Read the XML file and add the model_file element
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Insert model_file after the opening InverseKinematicsTool tag
        import_line = '\t\t<model_file>{}</model_file>\n'.format(self.model_file)
        content = content.replace(
            '<InverseKinematicsTool',
            '<InverseKinematicsTool',
            1
        )
        # Find the end of the opening tag and insert after it
        tag_end = content.find('>', content.find('<InverseKinematicsTool'))
        if tag_end != -1:
            # Insert after results_directory if it exists, otherwise after the opening tag
            results_dir_pos = content.find('</results_directory>')
            if results_dir_pos != -1:
                insert_pos = results_dir_pos + len('</results_directory>') + 1
            else:
                insert_pos = tag_end + 1
                if content[insert_pos] == '\n':
                    insert_pos += 1
            
            content = content[:insert_pos] + import_line + content[insert_pos:]
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        return filepath
    
    def run(self) -> IKResult:
        """Execute IK analysis using XML-based workflow.
        
        Save settings to XML, load tool from XML (which loads the model), then run.
        
        Returns
        -------
        IKResult
            Structured IK results with motion file path and metadata
        """
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
            tool = InverseKinematicsTool(setup_file, True)  # True = load model
            
            # Execute tool
            tool.run()
            success = True
            
        except Exception as e:
            errors.append(str(e))
            setup_file = str(results_dir / "failed_setup.xml")
            raise RuntimeError(f"Tool execution failed: {e}") from e
            
        finally:
            end_time = datetime.now()
        
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
