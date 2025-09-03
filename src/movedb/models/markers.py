from sqlmodel import Field, Relationship, Column
from sqlalchemy import Interval
from .data_models import TimeSeriesData, DataSource
from typing import TYPE_CHECKING, Type
from datetime import timedelta

if TYPE_CHECKING:
    from .trial import Trial

class MarkerData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for marker data."""
    
    # Time series fields
    timestamp: timedelta = Field(sa_column=Column(Interval, primary_key=True, nullable=False))
    
    # Database fields
    parent_id: int = Field(foreign_key="marker.id", primary_key=True)
    parent: "Marker" = Relationship(back_populates="data")
    
    # Data fields
    x: float
    y: float
    z: float
    residual: float
    
class Marker(DataSource, table=True):
    """Concrete implementation of DataSource for marker data."""
    __mapper_args__ = {"polymorphic_identity": "marker"}
    # Database fields
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates="markers")
    
    # Data fields
    units: str = "m"
    
    # Relationship to time series data
    data: list[MarkerData] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type[MarkerData]:
        return MarkerData
    