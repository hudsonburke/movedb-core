from sqlmodel import Field, Relationship
from .data_models import HypertableData, DataSource
from .trial import Trial
from typing import Type
from functools import cached_property

class AnalogData(HypertableData["Analog"], table=True):
    value: float

class Analog(DataSource[AnalogData], table=True):
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: Trial | None = Relationship(back_populates = "analogs")
 
    units: str = "V"
    scale: float = 1.0
    offset: float = 0.0

    @property
    def _data_model(self) -> Type["AnalogData"]:
        return AnalogData

    @cached_property
    def _data_records(self) -> list[dict]:
        return [
            {"timestamp": d.timestamp, "value": (d.value - self.offset) * self.scale} # C3D Documentation p.73 
            for d in self._data
        ]
