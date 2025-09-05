from sqlmodel import Field, Relationship
from .data_models import TimeSeriesData, DataSource
from functools import cached_property
from typing import TYPE_CHECKING, Type
from datetime import timedelta

if TYPE_CHECKING:
    from .trial import Trial

class Analog(DataSource, table=True):
    id: int | None = Field(default=None, primary_key=True)

    trial_id: int | None = Field(default=None, foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates="analogs")

    units: str = "V"
    scale: float = 1.0
    offset: float = 0.0
    
    data: list["AnalogData"] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type["AnalogData"]:
        """Return the AnalogData model class."""
        return AnalogData

    @cached_property
    def _data_records(self) -> list[dict]:
        """Overrides DataSource._data_records to apply scaling and offset."""
        return [
            {
            "timestamp": d.timestamp,
            "value": (d.value - self.offset) * self.scale # C3D Documentation p.73
            }
            for d in self.data
        ]

class AnalogData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for analog data."""
    parent_id: int = Field(foreign_key="analog.id", primary_key=True)
    parent: Analog = Relationship(back_populates="data")
    
    timestamp: timedelta = Field(primary_key=True)
    value: float
