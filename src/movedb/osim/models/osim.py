from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict, Any
import datetime
from ...models.files import File

class OpenSimModel(File, table=True):
    """OpenSim model file with metadata."""
    
    model_name: str = Field(description="Descriptive name of the model")
    description: Optional[str] = Field(default=None, description="Model description")
    
    # Model structure metadata (cached from analysis)
    num_joints: Optional[int] = Field(default=None)
    num_muscles: Optional[int] = Field(default=None) 
    num_coordinates: Optional[int] = Field(default=None)
    joint_names: Optional[List[str]] = Field(default=None, sa_column_kwargs={"type_": "JSON"})
    muscle_names: Optional[List[str]] = Field(default=None, sa_column_kwargs={"type_": "JSON"})
    coordinate_names: Optional[List[str]] = Field(default=None, sa_column_kwargs={"type_": "JSON"})
    
    # Relationships
    analyses: List["OpenSimAnalysis"] = Relationship(back_populates="model")

class OpenSimAnalysis(SQLModel, table=True):
    """Base class for OpenSim analyses."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_name: str = Field(description="User-defined name for the analysis")
    analysis_type: str = Field(description="Type of analysis (IK, ID, CMC, etc.)")
    
    # Foreign keys
    model_id: int = Field(foreign_key="file.id")  # References OpenSimModel which inherits from File
    trial_id: Optional[int] = Field(default=None, foreign_key="trial.id")
    
    # Analysis status
    status: str = Field(default="queued", description="queued, running, completed, failed")
    progress: Optional[float] = Field(default=None, ge=0, le=1, description="Progress 0-1")
    message: Optional[str] = Field(default=None, description="Status message or error")
    
    # Timestamps
    date_created: datetime.datetime = Field(default_factory=datetime.datetime.now)
    date_started: Optional[datetime.datetime] = Field(default=None)
    date_completed: Optional[datetime.datetime] = Field(default=None)
    
    # Configuration (stored as JSON)
    config: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSON"})
    
    # Relationships
    model: OpenSimModel = Relationship(back_populates="analyses")
    results: List["OpenSimResults"] = Relationship(back_populates="analysis")

class OpenSimResults(File, table=True):
    """Results file from OpenSim analysis."""
    
    # Foreign key to analysis
    analysis_id: int = Field(foreign_key="opensimanalysis.id")
    
    # Result metadata
    result_type: str = Field(description="Type of result (angles, moments, forces, etc.)")
    units: Optional[str] = Field(default=None, description="Units of the data")
    
    # Data shape information
    num_frames: Optional[int] = Field(default=None)
    num_columns: Optional[int] = Field(default=None)
    column_names: Optional[List[str]] = Field(default=None, sa_column_kwargs={"type_": "JSON"})
    
    # Time range
    start_time: Optional[float] = Field(default=None)
    end_time: Optional[float] = Field(default=None)
    
    # Relationship
    analysis: OpenSimAnalysis = Relationship(back_populates="results")

class OpenSimIKSetup(OpenSimAnalysis, table=True):
    """Inverse Kinematics analysis setup."""
    
    # Time range for analysis
    start_time: Optional[float] = Field(default=None)
    end_time: Optional[float] = Field(default=None)
    
    # Marker weights (stored as JSON)
    marker_weights: Optional[Dict[str, float]] = Field(default=None, sa_column_kwargs={"type_": "JSON"})
    
    # IK-specific settings
    accuracy: float = Field(default=1e-5)
    constraint_weight: float = Field(default=20.0)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.analysis_type = "inverse_kinematics"

class OpenSimIDSetup(OpenSimAnalysis, table=True):
    """Inverse Dynamics analysis setup."""
    
    # Reference to IK results
    ik_results_id: int = Field(foreign_key="file.id")  # References OpenSimResults which inherits from File
    
    # ID-specific settings
    lowpass_freq: float = Field(default=-1, description="Lowpass filter frequency, -1 for no filtering")
    forces_to_exclude: Optional[List[str]] = Field(default=None, sa_column_kwargs={"type_": "JSON"})
    
    # External loads file
    external_loads_file: Optional[str] = Field(default=None)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.analysis_type = "inverse_dynamics"

class OpenSimIKResults(OpenSimResults, table=True):
    """Specific results from Inverse Kinematics."""
    
    # IK-specific metrics
    marker_error_rms: Optional[float] = Field(default=None, description="RMS marker error")
    max_marker_error: Optional[float] = Field(default=None, description="Maximum marker error")
    
    def __init__(self, **data):
        super().__init__(**data)
        self.result_type = "joint_angles"
        self.units = "degrees"

class OpenSimIDResults(OpenSimResults, table=True):
    """Specific results from Inverse Dynamics."""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.result_type = "joint_moments"
        self.units = "N-m"

# Additional analysis types can be added as needed:
# class OpenSimCMCSetup(OpenSimAnalysis, table=True):
# class OpenSimSOSetup(OpenSimAnalysis, table=True):
# class OpenSimFDSetup(OpenSimAnalysis, table=True):
# class OpenSimRRASetup(OpenSimAnalysis, table=True):

