from sqlmodel import Field, Relationship
from .data_models import DataSource, TimeSeriesData
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .trial import Trial

class MarkerData(TimeSeriesData["Marker"], table=True):
    """Concrete implementation of TimeSeriesData for marker data."""
    
    # Database fields
    parent_id: int = Field(foreign_key="marker.id", primary_key=True)
    parent: "Marker" = Relationship(back_populates="data")
    
    # Data fields
    x: float
    y: float
    z: float
    residual: float
    
    # Abstract methods are satisfied by the field definitions above

class Marker(DataSource[MarkerData], table=True):
    """Concrete implementation of DataSource for marker data."""
    
    # Database fields
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates="markers")
    
    # Data fields
    units: str = "m"
    
    # Relationship to time series data
    _data: list[MarkerData] = Relationship(back_populates="parent")
    