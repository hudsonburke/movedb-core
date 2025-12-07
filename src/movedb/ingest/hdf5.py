import h5py as h5
import numpy as np
from pydantic import BaseModel
from pathlib import Path
from typing import Callable, Any, Type, TypeVar

h5.get_config().track_order = True


class H5LoadRegistry:
    def __init__(self):
        self.type_map: dict[type, Callable] = {
            bytes: lambda x: x.decode("utf-8"),
            np.bytes_: lambda x: x.decode("utf-8"),
            # Add other specific scalar types if needed
        }

        self.dtype_map: dict[str, Callable] = {
            "S": self._decode_string_array,
            "U": self._decode_unicode_array,
            "O": self._decode_object_array,
            # 'f' and 'i' usually default to "pass through"
        }

    def convert(self, value: Any) -> Any:
        value_type = type(value)
        converter = self.type_map.get(value_type)
        if converter:
            return converter(value)
        if hasattr(value, "dtype"):
            dtype_str = value.dtype.kind
            converter = self.dtype_map.get(dtype_str)
            if converter:
                return converter(value)
            if value.ndim == 0:
                return value.item()

    def register_type(self, py_type: type, converter: Callable) -> None:
        self.type_map[py_type] = converter

    def register_dtype(self, dtype_str: str, converter: Callable) -> None:
        self.dtype_map[dtype_str] = converter

    @staticmethod
    def _decode_string_array(arr: np.ndarray) -> list[str]:
        # Decodes fixed-length byte strings (S)
        return [x.decode("utf-8") for x in arr.flatten()]

    @staticmethod
    def _decode_unicode_array(arr: np.ndarray) -> list[str]:
        # Handles already unicode strings (U)
        return [str(x) for x in arr.flatten()]

    @staticmethod
    def _decode_object_array(arr: np.ndarray) -> list[str] | np.ndarray:
        # 'Object' arrays are tricky. Usually variable-length strings in HDF5.
        # Check the first element to see if it's bytes
        if arr.size > 0 and isinstance(arr.flat[0], (bytes, np.bytes_)):
            return [x.decode("utf-8") for x in arr.flatten()]
        return arr


decoder = H5LoadRegistry()


def _h5_to_dict(group: h5.Group) -> dict:
    result = {}

    # Fast loop over attributes
    for k, v in group.attrs.items():
        result[k] = decoder.convert(v)

    # Fast loop over datasets
    for k, item in group.items():
        if isinstance(item, h5.Group):
            result[k] = _h5_to_dict(item)
        elif isinstance(item, h5.Dataset):
            # Only read the data from disk now
            val = item[()]
            result[k] = decoder.convert(val)

    return result


T = TypeVar("T", bound="BaseModel")


def load_from_hdf5(path: str, model_cls: Type[T]) -> T:
    with h5.File(path, "r") as f:
        data = _h5_to_dict(f)
    return model_cls(**data)


class H5WriteRegistry:
    def __init__(self):
        self.type_map: dict[type, Callable] = {}

    def convert(self, value: Any) -> Any:
        value_type = type(value)
        writer = self.type_map.get(value_type)
        if writer:
            return writer(value)

    def register_type(self, py_type: type, writer: Callable) -> None:
        self.type_map[py_type] = writer


writer = H5WriteRegistry()


def save_to_hdf5(model: BaseModel, path: str | Path) -> None:
    """Entry point to save a Pydantic model to HDF5."""
    with h5.File(path, "w") as f:
        _write_group(f, model)


def _write_group(
    group: h5.Group, model: BaseModel, exclude_fields: set[str] | None = None
) -> None:
    """Recursive helper to write fields to a group."""
    model_dict = model.model_dump(exclude=exclude_fields)
    # Iterate over the model's fields directly
    for field_name in model_dict.keys():
        value = getattr(model, field_name)

        if value is None:
            continue

        # 1. Nested Pydantic Model -> New Group
        if isinstance(value, BaseModel):
            subgroup = group.create_group(field_name)
            _write_group(subgroup, value)

        # 2. Numpy Array -> Dataset
        elif isinstance(value, np.ndarray):
            group.create_dataset(field_name, data=value, compression="gzip")

        elif isinstance(value, dict):
            subgroup = group.create_group(field_name)
            for k, v in value.items():
                if isinstance(v, (int, float, str)):
                    subgroup.attrs[k] = v

        elif isinstance(value, (int, float, str, bool)):
            group.attrs[field_name] = value
