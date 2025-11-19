"""Abstract tool settings base class (DEPRECATED).

This module is deprecated and kept only for backwards compatibility.
All tool classes (ScaleSettings, IKSettings, IDSettings, CMCSettings) have been
refactored to be independent and no longer inherit from AbstractToolSettings.

Only CMCTool actually inherits from AbstractTool in OpenSim's C++ API, so forcing
all tools to inherit from a shared base class was an unnecessary architectural constraint.
"""

from pyopensim.simulation import AnalysisSet, ControllerSet, AbstractTool
from pyopensim.common import ArrayStr
from pydantic import BaseModel, Field, ConfigDict
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .results import ToolResult

class AbstractToolSettings(BaseModel):
    """Abstract base class for tool settings.
    
    .. deprecated::
        This class is deprecated and no longer used internally. All tool settings
        classes (ScaleSettings, IKSettings, IDSettings, CMCSettings) are now
        independent and inherit directly from Pydantic's BaseModel.
        
        This class is kept for backwards compatibility only.

    Descriptions are available in Field(...) metadata for runtime/schema usage.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    model_file: str = Field(
        ...,
        description="Name of the .osim file used to construct a model.",
    )
    results_directory: str = Field(
        ".", description="Directory used for writing results."
    )
    initial_time: float = Field(
        -1.0, description="Initial time for the simulation."
    )
    final_time: float = Field(
        -1.0, description="Final time for the simulation."
    )
    replace_force_set: bool = Field(
        False,
        description=(
            "Replace the model's force set with sets specified in "
            "<force_set_files>? If false, the force set is appended to."
        ),
    )
    output_precision: int = Field(
        8, description="Output precision. It is 8 by default."
    )
    external_loads_file: str = Field(
        "",
        description=(
            "XML file (.xml) containing the forces applied to the model as "
            "ExternalLoads."
        ),
    )
    analysis_set: AnalysisSet | None = Field(
        None, description="Set of analyses to be run during the investigation."
    )
    controller_set: ControllerSet | None = Field(
        None, description="Controller objects in the model."
    )
    force_set_files: list[str] = Field(
        default_factory=list,
        description="List of xml files used to construct a force set for the model.",
    )

    def to_xml(self, root_element_name = "AbstractTool") -> str:
        """Convert the settings to an XML representation.

        Returns
        -------
        str
            XML string representing the settings.
        """
        # This is a placeholder implementation. Actual implementation would
        # convert each field to its corresponding XML representation.
        # TODO: Also add descriptions as comments in the XML.
        xml_elements = []
        for field_name, field_value in self.model_dump().items():
            xml_elements.append(f"<{field_name}>{field_value}</{field_name}>")
        return f"<{root_element_name}>\n" + "\n".join(xml_elements) + f"\n</{root_element_name}>"
    
    @abstractmethod
    def _create_tool_instance(self) -> AbstractTool:
        """Create the specific tool instance (e.g., CMCTool, RRATool).
        
        Subclasses must implement this to return their specific tool type.
        
        Returns
        -------
        AbstractTool
            A new instance of the specific OpenSim tool.
        """
        pass
    
    def _configure_common_settings(self, tool: AbstractTool) -> None:
        """Configure settings common to all OpenSim tools.
        
        Parameters
        ----------
        tool : AbstractTool
            The tool instance to configure.
        """
        tool.setModelFilename(self.model_file)
        tool.setResultsDir(self.results_directory)
        tool.setInitialTime(self.initial_time)
        tool.setFinalTime(self.final_time)
        tool.setReplaceForceSet(self.replace_force_set)
        tool.setOutputPrecision(self.output_precision)
        tool.setExternalLoadsFileName(self.external_loads_file)
        
        # Convert Python list to OpenSim ArrayStr
        if self.force_set_files:
            force_set_array = ArrayStr()
            for file_path in self.force_set_files:
                force_set_array.append(file_path)
            tool.setForceSetFiles(force_set_array)
        else:
            tool.setForceSetFiles(ArrayStr())  # Empty array
    
    def _configure_tool_specific_settings(self, tool: AbstractTool) -> None:
        """Configure tool-specific settings.
        
        Subclasses can override this to add their specific configurations.
        
        Parameters
        ----------
        tool : AbstractTool
            The tool instance to configure.
        """
        pass
    
    def create_tool(self) -> AbstractTool:
        """Create an OpenSim tool based on the settings.

        Returns
        -------
        AbstractTool
            An instance of an OpenSim tool configured with the settings.
        """
        # Create the specific tool instance
        tool = self._create_tool_instance()
        
        # Configure common settings
        self._configure_common_settings(tool)
        
        # Configure tool-specific settings
        self._configure_tool_specific_settings(tool)
        
        return tool
    
    def save_setup(self, filepath: str | None = None) -> str:
        """Save tool setup to XML file.
        
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
            results_dir = Path(self.results_directory)
            results_dir.mkdir(parents=True, exist_ok=True)
            tool_name = self.__class__.__name__.replace('Settings', '').lower()
            filepath = str(results_dir / f"{tool_name}_setup.xml")
        
        tool.printToXML(filepath)
        return filepath
    
    @abstractmethod
    def _create_result(
        self,
        setup_file: str,
        success: bool,
        start_time: datetime,
        end_time: datetime,
        warnings: list[str],
        errors: list[str],
    ) -> "ToolResult":
        """Create a result object specific to this tool.
        
        Subclasses must implement this to return their specific result type.
        
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
        ToolResult
            Tool-specific result object
        """
        pass
    
    def run(self) -> "ToolResult":
        """Execute the tool and return results.
        
        This method:
        1. Validates settings
        2. Creates and configures the tool
        3. Saves setup XML
        4. Executes the tool
        5. Returns structured results
        
        Returns
        -------
        ToolResult
            Structured results with metadata and output file paths
            
        Raises
        ------
        ValueError
            If settings validation fails
        RuntimeError
            If tool execution fails
        """
        # Ensure results directory exists
        results_dir = Path(self.results_directory)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        warnings = []
        errors = []
        success = False
        start_time = datetime.now()
        
        try:
            # Create and configure tool
            tool = self.create_tool()
            
            # Save setup XML
            setup_file = self.save_setup()
            
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
