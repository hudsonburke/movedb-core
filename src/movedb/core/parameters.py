"""Base models for typed session parameters."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class SessionParameters(BaseModel):
    """Minimum session-parameter contract with room for dataset-specific fields.

    Subclasses add typed study- or pipeline-specific parameter fields. Unknown
    keys are accepted and preserved as extras so raw sources can evolve without
    blocking ingestion.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    schema_version: ClassVar[str] = "0.1.0"

    subject_id: str | None = None
    session_id: str | None = None
    source_file: str | None = None

    @property
    def extras(self) -> dict[str, Any]:
        return dict(self.model_extra or {})

    @classmethod
    def schema_name(cls) -> str:
        return cls.__name__

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly payload with extras nested under `extras`."""

        data = self.model_dump(mode="json")
        extras = {key: data.pop(key) for key in list(data) if key not in type(self).model_fields}
        if extras:
            data["extras"] = extras
        return data

    def to_record(self) -> dict[str, Any]:
        """Return a flat row suitable for Parquet storage."""

        payload = self.to_payload()
        extras = payload.pop("extras", None)
        payload["parameter_schema"] = type(self).schema_name()
        payload["parameter_schema_version"] = type(self).schema_version
        payload["extras_json"] = json.dumps(extras, sort_keys=True) if extras else None
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SessionParameters":
        """Build a typed parameter model from JSON or Parquet payloads."""

        data = dict(payload)
        extras = data.pop("extras", None)
        extras_json = data.pop("extras_json", None)
        data.pop("parameter_schema", None)
        data.pop("parameter_schema_version", None)

        if isinstance(extras_json, str) and extras is None:
            extras = json.loads(extras_json)
        if isinstance(extras, dict):
            data.update(extras)

        return cls.model_validate(data)
