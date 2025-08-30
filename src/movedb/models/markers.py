from sqlmodel import Field, Relationship
from .trial import Trial
from .data_models import DataSource, HypertableData

class MarkerData(HypertableData["Marker"], table=True):
    x: float
    y: float
    z: float
    residual: float

class Marker(DataSource[MarkerData], table=True):
    trial_id: int | None = Field(default = None, foreign_key="trial.id")
    trial: Trial | None = Relationship(back_populates="markers")

    units: str = "m"
    