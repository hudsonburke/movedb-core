from sqlmodel import Field, Relationship, Column
from sqlalchemy import Interval
from .data_models import TimeSeriesData, DataSource
from typing import TYPE_CHECKING, Type
from datetime import timedelta

if TYPE_CHECKING:
    from .trial import Trial

class MarkerData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for marker data."""
    
    timestamp: timedelta = Field(primary_key=True)
    
    parent_id: int = Field(foreign_key="marker.id", primary_key=True)
    parent: "Marker" = Relationship(back_populates="data")
    
    x: float
    y: float
    z: float
    residual: float
    
class Marker(DataSource, table=True):
    """Concrete implementation of DataSource for marker data."""
    id: int | None = Field(default=None, primary_key=True)

    trial_id: int | None = Field(default=None, foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates="markers")

    units: str = "m"
    
    data: list[MarkerData] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type[MarkerData]:
        return MarkerData
    