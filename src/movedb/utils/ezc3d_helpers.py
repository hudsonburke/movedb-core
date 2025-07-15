from typing import Any

import ezc3d
import numpy as np


def get_c3d_param(
    c3d_object: ezc3d.c3d, *keys, index: int | None = None, default=None
) -> Any:
    """
    Helper function to get nested parameters from a C3D object.
    """
    param: dict = c3d_object.parameters
    for key in keys:
        param = param.get(key, {})
    value = param.get("value", {})
    if index is not None and (isinstance(value, list) or isinstance(value, np.ndarray)):
        if index < 0 or index >= len(value):
            raise IndexError(f"Index {index} out of range for parameter '{keys}'.")
        return value[index]
    return value if value is not None else default
