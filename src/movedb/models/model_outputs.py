from .data_models import TimeSeriesData, DataSource
from sqlmodel import Field, Relationship

class AngleData(TimeSeriesData["Angle"], table=True):
    """Concrete implementation of TimeSeriesData for angle data."""
    
    # Database fields
    parent_id: int = Field(foreign_key="angle.id", primary_key=True)
    parent: "Angle" = Relationship(back_populates="data")
    
    # Data fields
    angle: float

class Angle(DataSource[AngleData], table=True):
    """Concrete implementation of DataSource for angle data."""
    
    # Data fields
    units: str = "degrees"
    
    # Relationship to time series data
    _data: list[AngleData] = Relationship(back_populates="parent")


class MomentData(TimeSeriesData["Moment"], table=True):
    """Concrete implementation of TimeSeriesData for moment data."""
    
    # Database fields
    parent_id: int = Field(foreign_key="moment.id", primary_key=True)
    parent: "Moment" = Relationship(back_populates="data")
    
    # Data fields
    moment: float

class Moment(DataSource[MomentData], table=True):
    """Concrete implementation of DataSource for moment data."""
    
    # Data fields
    units: str = "Nm"
    
    # Relationship to time series data
    _data: list[MomentData] = Relationship(back_populates="parent")