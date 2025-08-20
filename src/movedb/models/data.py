from sqlalchemy import DateTime, ForeignKey, Column, Integer
from sqlalchemy.orm import declared_attr, Mapped, MappedColumn, Relationship
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Type, cast, TypeVar
from abc import ABC, abstractmethod
import polars as pl
import pandas as pd

T = TypeVar("T", bound="HypertableData")

class HypertableData[ParentT](SQLModel):
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), primary_key=True, nullable=False)
    )

    @declared_attr
    def parent_id(cls) -> Mapped[int]:
        parent_table_name = cls.__name__.lower().replace("data", "")
        return MappedColumn(Integer, ForeignKey(f"{parent_table_name}.id"), primary_key=True)

    @declared_attr
    def parent(cls) -> Mapped[ParentT]:
        return Relationship(back_populates="data")

class DataSource[T](SQLModel, ABC):
    id: int | None = Field(default=None, primary_key=True)
    name: str | None = Field(default=None, index=True)
    description: str = ""
    rate: float
    first_frame: int

    data: list[T] = cast(list[T], Relationship(back_populates="parent"))

    @property
    @abstractmethod
    def _data_model(self) -> Type[T]:
        raise NotImplementedError

    def set_data(self, value: pl.DataFrame | pd.DataFrame | list[T]):
        if isinstance(value, pl.DataFrame):
            model_class = self._data_model
            self.data = [model_class(**row) for row in value.to_dicts()]
        elif isinstance(value, pd.DataFrame):
            if value.index.name == 'timestamp':
                value = value.reset_index()
            model_class = self._data_model
            self.data = [model_class(**{str(k): v for k, v in row.items()}) for row in value.to_dict(orient='records')]
        elif isinstance(value, list):
            self.data = value
        else:
            raise TypeError("Data must be a polars DataFrame, a pandas DataFrame, or a list of data model instances.")

    def __len__(self):
        return len(self.data)

    @abstractmethod
    def _get_data_records(self) -> list[dict]:
        raise NotImplementedError

    def to_pandas(self) -> pd.DataFrame:
        records = self._get_data_records()
        if not records:
            return pd.DataFrame()
        return pd.DataFrame.from_records(records).set_index('timestamp')

    # TODO: Could be a cached_property? -> assumes immutability
    def to_polars(self) -> pl.DataFrame:
        records = self._get_data_records()
        if not records:
            return pl.DataFrame()
        return pl.from_records(records)

