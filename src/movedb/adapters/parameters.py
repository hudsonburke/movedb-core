"""Generic parameter extraction and persistence.

This module is source-agnostic: it takes a raw ``dict[str, str]`` (produced by
any parser — e.g. :func:`movedb.adapters.vicon.parse_mp_file`) and validates it
against a user-defined Pydantic model.

Two strategies for mapping source keys to model fields:

1. **Aliases** (zero-config) — Define ``Field(alias=...)`` on the model and set
   ``model_config = ConfigDict(populate_by_name=True)``.  Pydantic resolves
   aliases automatically.

2. **Explicit mapping** — Pass a ``mapping`` dict to :func:`extract_parameters`.
   Source keys are translated to model field names before validation.  This
   takes precedence over aliases when provided.

Example user-defined model::

    from pydantic import BaseModel, ConfigDict, Field

    class HumanParams(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        mass: float = Field(alias="bodymass")
        height: float = Field(alias="height")
        leg_length: float | None = Field(default=None, alias="leftleglength")

Example usage::

    from movedb.adapters.vicon import parse_mp_file
    from movedb.adapters.parameters import extract_parameters, write_parameters

    raw = parse_mp_file("session.mp")
    params = extract_parameters(raw, HumanParams)
    write_parameters(params, "sub-01/ses-01/parameters.json")
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def extract_parameters(
    source: dict[str, str],
    model: type[T],
    mapping: dict[str, str] | None = None,
) -> T:
    """Extract and validate parameters from a raw key-value source.

    Parameters
    ----------
    source
        Raw key-value dict (e.g. from ``parse_mp_file``).  All values are
        typically strings; Pydantic handles type coercion.
    model
        A Pydantic ``BaseModel`` subclass defining the expected parameter
        schema.  Fields may use ``Field(alias=...)`` for source-key mapping.
    mapping
        Optional dict mapping **source keys** to **model field names**.
        When provided, only keys present in the mapping are forwarded and
        aliases on the model are bypassed.

    Returns
    -------
    T
        A validated instance of *model*.

    Raises
    ------
    pydantic.ValidationError
        If required fields are missing or values cannot be coerced.
    """
    if mapping is not None:
        data = {mapping[k]: v for k, v in source.items() if k in mapping}
        return model.model_validate(data)
    return model.model_validate(source)


def write_parameters(params: BaseModel, path: str | Path) -> None:
    """Write a validated parameter model to a JSON file.

    Parameters
    ----------
    params
        A Pydantic model instance to serialize.
    path
        Destination file path (e.g. ``sub-01/ses-01/parameters.json``).
    """
    from ..storage.parameters import write_parameters_json
    write_parameters_json(params, path)


def read_parameters(path: str | Path, model: type[T]) -> T:
    """Read parameters from a JSON file and validate against a model.

    Parameters
    ----------
    path
        Path to the JSON file written by :func:`write_parameters`.
    model
        The Pydantic model class to validate against.

    Returns
    -------
    T
        A validated instance of *model*.
    """
    from ..storage.parameters import read_parameters_json
    return read_parameters_json(path, model)
