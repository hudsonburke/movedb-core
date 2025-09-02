from sqlmodel import Field, Relationship
from .data_models import TimeSeriesData, DataSource
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .trial import Trial

class AnalogData(TimeSeriesData["Analog"], table=True):
    """Concrete implementation of TimeSeriesData for analog data."""
    
    # Database fields
    parent_id: int = Field(foreign_key="analog.id", primary_key=True)
    parent: "Analog" = Relationship(back_populates="data")
    
    # Data fields
    value: float

class Analog(DataSource[AnalogData], table=True):
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates = "analogs")
 
    units: str = "V"
    scale: float = 1.0
    offset: float = 0.0
    
    # Relationship to time series data
    _data: list[AnalogData] = Relationship(back_populates="parent")

    @cached_property # Overrides DataSource._data_records to apply scaling and offset
    def _data_records(self) -> list[dict]:
        return [
            {"timestamp": d.timestamp, "value": (d.value - self.offset) * self.scale} # C3D Documentation p.73 
            for d in self._data
        ]
