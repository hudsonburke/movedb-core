from sqlalchemy import ForeignKey, Column, Integer, Interval
from sqlalchemy.orm import declared_attr, Mapped, MappedColumn, Relationship
from sqlmodel import SQLModel, Field
from pydantic import model_validator
from datetime import timedelta
from typing import Type, cast, Any
from abc import ABC, abstractmethod
import polars as pl
import pandas as pd

class HypertableData[ParentT](SQLModel):
    timestamp: timedelta = Field(
        sa_column=Column(Interval, primary_key=True, nullable=False)
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
    last_frame: int | None = None

    _data: list[T] = cast(list[T], Relationship(back_populates="parent"))

    data: Any = Field(default=None, exclude=True)

    @property
    @abstractmethod
    def _data_model(self) -> Type[T]:
        raise NotImplementedError

    @classmethod # TODO: Better type hint for data
    def convert_data(cls, data: Any, instance: "DataSource[T]") -> list[T]:
        """
        Converts various data formats into a list of dictionaries.
        """
        data_model = instance._data_model
        match data:
            case pl.DataFrame():
                return [data_model(**row) for row in data.to_dicts()]
            case pd.DataFrame():
                if data.index.name == 'timestamp':
                    data = data.reset_index()
                return [data_model(**{str(k): v for k, v in row.items()}) 
                        for row in data.to_dict(orient='records')]
            case list() if all(isinstance(item, data_model) for item in data):
                return data
            case list() if all(isinstance(item, dict) for item in data):
                return [data_model(**item) for item in data]
            case None:
                return []
            case _:
                raise TypeError(
                    f"Unsupported data type: {type(data).__name__}. "
                    "Must be a polars/pandas DataFrame, a list of dicts, "
                    "or a list of {data_model.__name__} instances."
                )

    @model_validator(mode='before')
    @classmethod
    def _validate_and_set_data(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Catches the 'data' field during initialization, converts it to model
        instances, and assigns it to the '_data' relationship field.
        """
        if data_in := values.get("data"):
            concrete_class_instance = cls(**{k: v for k, v in values.items() if k != 'data'})
            values["_data"] = cls.convert_data(data_in, concrete_class_instance)
            # Remove the temporary 'data' field so SQLModel doesn't see it
            del values["data"]
        return values

    def set_data(self, data: Any) -> None:
        self._data = self.convert_data(data, self)

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
