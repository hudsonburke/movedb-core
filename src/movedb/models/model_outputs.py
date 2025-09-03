from .data_models import TimeSeriesData, DataSource
from sqlmodel import Field, Relationship, Column
from sqlalchemy import Interval
from typing import Type
from datetime import timedelta

class AngleData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for angle data."""
    
    # Time series fields
    timestamp: timedelta = Field(sa_column=Column(Interval, primary_key=True, nullable=False))
    
    # Database fields
    parent_id: int = Field(foreign_key="datasource.id", primary_key=True)
    parent: "Angle" = Relationship(back_populates="data")
    
    # Data fields
    angle: float

class Angle(DataSource, table=True):
    """Concrete implementation of DataSource for angle data."""
    __mapper_args__ = {"polymorphic_identity": "angle"}
    # Data fields
    units: str = "degrees"
    
    # Relationship to time series data
    data: list[AngleData] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type[AngleData]:
        return AngleData

class MomentData(TimeSeriesData, table=True):
    """Concrete implementation of TimeSeriesData for moment data."""
    
    # Time series fields
    timestamp: timedelta = Field(sa_column=Column(Interval, primary_key=True, nullable=False))
    
    # Database fields
    parent_id: int = Field(foreign_key="datasource.id", primary_key=True)
    parent: "Moment" = Relationship(back_populates="data")
    
    # Data fields
    moment: float

class Moment(DataSource, table=True):
    """Concrete implementation of DataSource for moment data."""
    __mapper_args__ = {"polymorphic_identity": "moment"}
    # Data fields
    units: str = "Nm"
    
    # Relationship to time series data
    data: list[MomentData] = Relationship(back_populates="parent")

    @classmethod
    def _get_data_model(cls) -> Type[MomentData]:
        return MomentData