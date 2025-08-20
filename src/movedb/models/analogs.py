from sqlmodel import Field, Relationship
from .data import HypertableData, DataSource
from .trial import Trial
from typing import Type

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

    def _get_data_records(self) -> list[dict]:
        return [
            {"timestamp": d.timestamp, "value": (d.value * self.scale + self.offset)}
            for d in self.data
        ]
