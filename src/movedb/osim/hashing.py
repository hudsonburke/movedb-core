"""Canonical JSON and run ID hashing utilities."""

from __future__ import annotations

import hashlib
import json


def canonical_json(params: dict) -> str:
    """Return canonical JSON representation of parameters.
    
    Uses JSON with sorted keys and compact separators for deterministic
    serialization across different key orderings.
    
    Raises ValueError if any value is NaN (due to allow_nan=False).
    """
    return json.dumps(params, sort_keys=True, separators=(',', ':'), allow_nan=False)


def parameter_hash(params: dict) -> str:
    """Return SHA256 hash of canonical JSON parameters as 64-char hex string."""
    canonical = canonical_json(params)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def short_run_id(params: dict) -> str:
    """Return first 12 characters of parameter_hash for compact run identification."""
    return parameter_hash(params)[:12]
