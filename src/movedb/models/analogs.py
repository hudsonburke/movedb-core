from sqlmodel import Field, Relationship, Column
from sqlalchemy import Interval
from .data_models import TimeSeriesData, DataSource
from functools import cached_property
from typing import TYPE_CHECKING, Type
from datetime import timedelta

if TYPE_CHECKING:
    from .trial import Trial

class AnalogData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for analog data."""
    
    # Time series fields
    timestamp: timedelta = Field(sa_column=Column(Interval, primary_key=True, nullable=False))
    
    # Database fields
    parent_id: int = Field(foreign_key="analog.id", primary_key=True)
    parent: "Analog" = Relationship(back_populates="data")
    
    # Data fields
    value: float

class Analog(DataSource, table=True):
    __mapper_args__ = {"polymorphic_identity": "analog"}
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates = "analogs")
 
    units: str = "V"
    scale: float = 1.0
    offset: float = 0.0
    
    # Relationship to time series data
    data: list[AnalogData] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type[AnalogData]:
        return AnalogData

    @cached_property
    def _data_records(self) -> list[dict]:
        """Overrides DataSource._data_records to apply scaling and offset."""
        return [
            {"timestamp": d.timestamp, "value": (d.value - self.offset) * self.scale} # C3D Documentation p.73 
            for d in self.data
        ]
