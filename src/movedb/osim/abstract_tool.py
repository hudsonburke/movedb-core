from pyopensim.simulation import AnalysisSet, ControllerSet, AbstractTool
from pydantic import BaseModel, Field
from abc import abstractmethod

class AbstractToolSettings(BaseModel):
    """Abstract base class for tool settings.

    Descriptions are available in Field(...) metadata for runtime/schema usage.
    """
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
        tool.setForceSetFiles(self.force_set_files)
    
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