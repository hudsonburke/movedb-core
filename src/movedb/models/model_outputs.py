from .data_models import TimeSeriesData, DataSource
from sqlmodel import Field, Relationship, Column
from sqlalchemy import Interval
from typing import Type
from datetime import timedelta

class AngleData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for angle data."""
    timestamp: timedelta = Field(primary_key=True)
    
    parent_id: int = Field(foreign_key="datasource.id", primary_key=True)
    parent: "Angle" = Relationship(back_populates="data")
    
    angle: float

class Angle(DataSource, table=True):
    """Concrete implementation of DataSource for angle data."""
    id: int | None = Field(default=None, primary_key=True)
    units: str = "degrees"
    
    data: list[AngleData] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type[AngleData]:
        return AngleData

class MomentData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for moment data."""
    timestamp: timedelta = Field(primary_key=True)
    
    parent_id: int = Field(foreign_key="datasource.id", primary_key=True)
    parent: "Moment" = Relationship(back_populates="data")
    
    moment: float

class Moment(DataSource, table=True):
    """Concrete implementation of DataSource for moment data."""
    id: int | None = Field(default=None, primary_key=True)
    units: str = "Nm"
    
    data: list[MomentData] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type[MomentData]:
        return MomentData