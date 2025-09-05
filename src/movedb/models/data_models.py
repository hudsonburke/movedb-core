from sqlmodel import SQLModel, Field
from pydantic import model_validator, field_validator
from datetime import timedelta
from typing import Any
from abc import ABC, abstractmethod
import polars as pl
import pandas as pd
from functools import cached_property


class TimeSeriesData(ABC, SQLModel):
    """Abstract base class for time series data.

    Concrete subclasses should define:
    timestamp: timedelta = Field(primary_key=True)
    parent_id: int = Field(foreign_key="parent_table.id", primary_key=True)
    parent: ParentDataSource = Relationship(back_populates="data")
    """
    timestamp: timedelta
    # NOTE: parent and parent_id must be defined in concrete subclasses

class DataSource(ABC, SQLModel):
    """Abstract base class for data sources.
    
    REQUIRED: Concrete subclasses MUST define:
    - data: list[ConcreteTimeSeriesData] = Relationship(back_populates="parent")
    - table=True (for SQLModel table creation)
    - _get_data_model() method returning the data model class
    
    Example:
        class Analog(DataSource, table=True):
            data: list[AnalogData] = Relationship(back_populates="parent")
            
            def _get_data_model(self):
                return AnalogData
    """
    #id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="", index=True)
    description: str = Field(default="")
    rate: float = Field(description="The rate of the data in Hz")
    first_frame: int
    last_frame: int | None = None
    # NOTE: 'data' and 'data_model' must be defined in concrete subclasses

    @classmethod
    @abstractmethod
    def _get_data_model(cls) -> type:
        """Return the data model class for this data source.
        
        This method MUST be implemented by concrete subclasses.
        
        Returns:
            The TimeSeriesData subclass for this data source.
        """
        pass
    
    def _invalidate_caches(self):
        """Invalidate cached properties."""
        for attr in ("_data_records", "to_polars", "to_pandas"):
            if attr in self.__dict__:
                del self.__dict__[attr]

    @classmethod
    def _convert_data_statically(cls, data: Any, data_model: type) -> list:
        # Accept polars/pandas DataFrame, list of models, list of dicts, or None
        if data is None:
            return []

        if isinstance(data, pl.DataFrame):
            return [data_model(**row) for row in data.to_dicts()]

        if isinstance(data, pd.DataFrame):
            # If timestamp is the index, move it back to a column so constructor sees it
            if data.index.name == 'timestamp':
                data = data.reset_index()
            return [data_model(**{str(k): v for k, v in row.items()}) for row in data.to_dict(orient='records')]

        if isinstance(data, list):
            if all(isinstance(item, data_model) for item in data):
                return data
            if all(isinstance(item, dict) for item in data):
                return [data_model(**item) for item in data]
            
        if isinstance(data, dict):
            return [data_model(**{str(k): v for k, v in data.items()})]

        raise TypeError(f"Unsupported data type: {type(data).__name__}.")

    @model_validator(mode='before')
    @classmethod
    def _validate_data(cls, values: Any) -> Any:
        """Pydantic validator to convert and set data before model instantiation."""
        # Only process if 'data' is provided and it's not already model instances
        if not isinstance(values, dict):
            return values
        data = values.get('data', None)
        if data is not None:
            # Get the data model from the class method
            data_model = cls._get_data_model()
            values['data'] = cls._convert_data_statically(data, data_model)
        return values
    
    @field_validator('data', mode='before', check_fields=False)
    @classmethod
    def _validate_data_field(cls, data: Any) -> Any:
        """Pydantic field validator to convert and set data when 'data' is assigned."""
        if data is not None:
            data_model = cls._get_data_model()
            return cls._convert_data_statically(data, data_model)
        return data
    
    def set_data(self, data: Any):
        """Set data from various formats and return self for chaining."""
        data_model = self._get_data_model()
        self.data = self._convert_data_statically(data, data_model)
        self._invalidate_caches()
        return self
 
    @cached_property
    def _data_records(self) -> list[dict]:
        return [
            d.model_dump(exclude={'parent', 'parent_id'})
            for d in getattr(self, "data", [])
        ]

    @cached_property
    def to_pandas(self) -> pd.DataFrame:
        records = self._data_records
        return pd.DataFrame.from_records(records).set_index('timestamp') if records else pd.DataFrame()

    @cached_property
    def to_polars(self) -> pl.DataFrame:
        records = self._data_records
        return pl.from_records(records) if records else pl.DataFrame()
