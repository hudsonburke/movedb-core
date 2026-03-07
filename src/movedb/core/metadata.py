"""Shared metadata models used across signal-specific metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field, PositiveFloat
from enum import Enum


class DataType(str, Enum):
    MARKERS = "markers"
    FORCEPLATES = "forceplates"
    ANALOGS = "analogs"


class _MetaBase(BaseModel):
    """Base class for signal metadata. Also serves as mixin for data models.

    Subclass this to define signal-specific metadata (e.g. ``MarkerMeta``),
    then subclass *that* to define the full data model (e.g. ``MarkerData``).
    Calling :meth:`metadata` on a data model instance returns a pure
    metadata instance with only the metadata fields.
    """

    # type: DataType = Field(
    #     description="Type of signal data (e.g., 'markers', 'forceplates', 'analogs')"
    # )
    rate: PositiveFloat = Field(description="Sampling rate in Hz")
    names: list[str] = Field(description="Signal / channel / plate names")

    def metadata(self) -> _MetaBase:
        """Return a pure metadata instance, stripping data-only fields."""
        meta_cls = next(
            cls
            for cls in type(self).__mro__
            if cls is not type(self)
            and issubclass(cls, _MetaBase)
            and cls is not _MetaBase
        )
        return meta_cls(**{k: getattr(self, k) for k in meta_cls.model_fields})

    def get_index(self, name: str) -> int:
        """Get the index by name."""
        try:
            return self.names.index(name)
        except ValueError:
            raise ValueError(f"Name '{name}' not found in list.")

    # TODO: Figure out how to get time and frames in here
