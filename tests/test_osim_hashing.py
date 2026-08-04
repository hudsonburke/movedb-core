"""Tests for canonical JSON hashing and run ID generation utilities."""

from __future__ import annotations

import pytest

from movedb.osim.hashing import canonical_json, parameter_hash, short_run_id


def test_canonical_json_returns_sorted_deterministic_string() -> None:
    """Known input should produce deterministic string with sorted keys."""
    params = {"accuracy": 1e-5, "model": "scaled.osim"}
    result = canonical_json(params)
    
    import json
    parsed = json.loads(result)
    assert parsed == params
    
    expected = '{"accuracy":1e-05,"model":"scaled.osim"}'
    assert result == expected


def test_canonical_json_key_reordering_invariance() -> None:
    """Different key orderings should produce identical canonical JSON."""
    params1 = {"b": 2, "a": 1}
    params2 = {"a": 1, "b": 2}
    
    assert canonical_json(params1) == canonical_json(params2)


def test_canonical_json_type_sensitivity() -> None:
    """Integers and floats should be distinguished in canonical JSON.
    
    This is intentional: {"x": 1} and {"x": 1.0} are semantically different
    in the context of run parameterization.
    """
    params_int = {"x": 1}
    params_float = {"x": 1.0}
    
    assert canonical_json(params_int) != canonical_json(params_float)


def test_canonical_json_rejects_nan() -> None:
    """NaN values should raise ValueError due to allow_nan=False."""
    params = {"x": float("nan")}
    
    with pytest.raises(ValueError):
        canonical_json(params)


def test_canonical_json_empty_dict() -> None:
    """Empty dict should produce valid JSON."""
    result = canonical_json({})
    assert result == "{}"


def test_parameter_hash_returns_64_char_hex() -> None:
    """parameter_hash should return a 64-character hexadecimal string (SHA256)."""
    params = {"accuracy": 1e-5, "model": "scaled.osim"}
    result = parameter_hash(params)
    
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_parameter_hash_is_deterministic_across_key_reordering() -> None:
    """Same parameters in different order should hash identically."""
    params1 = {"b": 2, "a": 1}
    params2 = {"a": 1, "b": 2}
    
    assert parameter_hash(params1) == parameter_hash(params2)


def test_parameter_hash_differs_for_different_params() -> None:
    """Different parameters should produce different hashes."""
    params1 = {"x": 1}
    params2 = {"x": 2}
    
    assert parameter_hash(params1) != parameter_hash(params2)


def test_parameter_hash_nested_dicts() -> None:
    """Nested dicts should be hashed deterministically."""
    params1 = {"settings": {"a": 1, "b": 2}}
    params2 = {"settings": {"b": 2, "a": 1}}
    
    assert parameter_hash(params1) == parameter_hash(params2)


def test_short_run_id_returns_12_chars() -> None:
    """short_run_id should return first 12 hex characters."""
    params = {"a": 1}
    result = short_run_id(params)
    
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_short_run_id_is_deterministic() -> None:
    """short_run_id should be deterministic."""
    params = {"accuracy": 1e-5, "model": "scaled.osim"}
    result1 = short_run_id(params)
    result2 = short_run_id(params)
    
    assert result1 == result2


def test_short_run_id_is_prefix_of_parameter_hash() -> None:
    """short_run_id should be the first 12 characters of parameter_hash."""
    params = {"x": 1}
    ph = parameter_hash(params)
    sri = short_run_id(params)
    
    assert sri == ph[:12]
