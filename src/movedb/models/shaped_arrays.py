# TODO: Clean up and unify shaped array types
# from numpydantic import NDArray, Shape
# from typing import TYPE_CHECKING
# FloatCol = tuple[float, ...]
#Tuple3 = tuple[float, float, float]
# Tuple3D = tuple[Tuple3, ...]
# Vector3D = NDArray[Shape["3"], float]  # pyright: ignore[reportInvalidTypeArguments]
# Vector = tuple[FloatCol, FloatCol, FloatCol]
# Matrix6x6 = NDArray[Shape["6, 6"], float]  # pyright: ignore[reportInvalidTypeArguments]
# Corners3x4 = NDArray[Shape["3, 4"], float]  # pyright: ignore[reportInvalidTypeArguments]

# General matrix types
# MatrixNx3 = NDArray[Shape["*, 3"], float]  # pyright: ignore[reportInvalidTypeArguments]
# Matrix3x3 = NDArray[Shape["3, 3"], float]  # pyright: ignore[reportInvalidTypeArguments]
# Matrix3xN = NDArray[Shape["3, *"], float]  # pyright: ignore[reportInvalidTypeArguments]

# CartesianTrajectory = NDArray[Shape["*, 3 xyz"], float]  # pyright: ignore[reportInvalidTypeArguments]

from pydantic import BeforeValidator
from typing import Annotated, Any
import numpy as np

def validate_shape(v, expected_shape: tuple[int, ...]) -> np.ndarray:
    """Validator that ensures the input is a NumPy array with a specific shape."""
    if isinstance(v, dict) and 'data' in v:
        # If it's already in DB format, convert it back for validation
        array = np.array(v['data'])
    elif not isinstance(v, np.ndarray):
        raise TypeError(f"Input must be a NumPy array, not {type(v).__name__}.")
    else:
        array = v

    if array.shape != expected_shape:
        raise ValueError(f"Array shape must be {expected_shape}, but got {array.shape}.")
    return array

CalMatrixArray = Annotated[np.ndarray, BeforeValidator(lambda v: validate_shape(v, (6,6)))]
CornersArray = Annotated[np.ndarray, BeforeValidator(lambda v: validate_shape(v, (3,4)))]
OriginArray = Annotated[np.ndarray, BeforeValidator(lambda v: validate_shape(v, (3,)))]
Matrix3x3 = Annotated[np.ndarray, BeforeValidator(lambda v: validate_shape(v, (3,3)))]


