from sqlmodel import Field, Relationship
from .trial import Trial
from .data_models import DataSource, HypertableData
from typing import Type
from functools import cached_property

class MarkerData(HypertableData["Marker"], table=True):
    x: float
    y: float
    z: float
    residual: float

class Marker(DataSource[MarkerData], table=True):
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: Trial | None = Relationship(back_populates="markers")

    units: str = "m"
    
    @property
    def _data_model(self) -> Type[MarkerData]:
        return MarkerData

    @cached_property
    def _data_records(self) -> list[dict]:
        return [
            {"timestamp": d.timestamp, "x": d.x, "y": d.y, "z": d.z, "residual": d.residual}
            for d in self._data
        ]

