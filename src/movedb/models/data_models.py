from sqlmodel import SQLModel, Field
from pydantic import model_validator
from datetime import timedelta
from typing import Type, Any, Protocol, TypeVar, Generic
import polars as pl
import pandas as pd
from functools import cached_property


class TimeSeriesData(SQLModel):
    """Abstract base class for time series data. 
    
    Concrete subclasses should define:
    timestamp: timedelta = Field(sa_column=Column(Interval, primary_key=True, nullable=False))
    """
    pass


class DataSource(SQLModel, table=True):
    """Abstract base class for data sources.
    NOTE: child classes should declare a SQLModel/SQLAlchemy relationship
    named `data: list[ConcreteData] = Relationship(...)`. We intentionally do
    not define a `data` property on the parent class to avoid a name
    collision with child class descriptors. Use `set_data(...)` to set
    input data (DataFrame/list/dicts) and the post-validator will attach the
    converted models to the child's relationship attribute.
    ----
    TODO: Update this whenever SQLModel merges polymorphism pull requests
    """
    
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default=None, index=True, unique=True)
    description: str = ""
    rate: float = Field(description="The rate of the data in Hz")
    first_frame: int
    last_frame: int | None = None
    
    type: str | None  = Field(default=None, index=True)  # discriminator

    __mapper_args__ = {
        "polymorphic_on": "type",
        "polymorphic_identity": "base",
    }
    
    def _invalidate_caches(self):
        """Invalidate cached properties."""
        for attr in ("_data_records", "to_polars", "to_pandas"):
            if attr in self.__dict__:
                del self.__dict__[attr]

    @classmethod
    def _get_data_model(cls) -> Type[TimeSeriesData]:
        raise NotImplementedError(f"{cls.__name__} must define the _get_data_model method")

    # --- Data Loading and Conversion ---
    @model_validator(mode='before')
    @classmethod
    def _validate_and_set_data(cls, values: dict[str, Any]) -> dict[str, Any]:
        # Accept explicit presence of the `data` key even when it's an empty list or None
        if "data" in values:
            data_in = values.pop("data")
            data_model = cls._get_data_model()
            values["data"] = cls._convert_data_statically(data_in, data_model)
        return values

    @classmethod
    def _convert_data_statically(cls, data: Any, data_model: Type[TimeSeriesData]) -> list[TimeSeriesData]:
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

        raise TypeError(f"Unsupported data type: {type(data).__name__}.")

    def set_data(self, data: Any):
        """Convenience method to set data and return self for chaining.

        Accepts the same input types as the `data` setter (pandas/polars/DataFrame,
        list of dicts, list of model instances, or None).
        """
        self.data = data
        # Invalidate cached properties
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

DataSourceType = TypeVar("DataSourceType", bound="DataSource")
TimeSeriesDataType = TypeVar("TimeSeriesDataType", bound="TimeSeriesData")

class TimeSeriesProtocol(Protocol):
    """Protocol defining the interface for time series data."""
    timestamp: timedelta

class DataSourceWithData(Protocol, Generic[TimeSeriesDataType]):
    data: list[TimeSeriesDataType]

class TimeSeriesDataWithParent(Protocol, Generic[DataSourceType]):
    timestamp: timedelta
    parent_id: int
    parent: DataSourceType
