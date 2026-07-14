from __future__ import annotations

from collections.abc import Collection
from typing import Any, Protocol

import polars as pl


class CatalogResult(Protocol):
    def fetchone(self) -> tuple[Any, ...] | None: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def pl(self) -> pl.DataFrame: ...


class CatalogConnection(Protocol):
    def execute(self, query: str, parameters: Collection[Any] | None = None) -> CatalogResult: ...
    def register(self, view_name: str, python_object: Any) -> CatalogConnection: ...
