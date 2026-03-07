import numpy as np
from numpydantic import NDArray
from typing import Literal  # Better for static type checking than numpydantic.Shape
from dataclasses import dataclass


@dataclass
class Vec3:
    x: float
    y: float
    z: float


@dataclass
class Vec3Array: ...


# Common
Array1D = NDArray[Literal["* frames"], np.float64]
NArray1D = NDArray[Literal["* frames, * n"], np.float64]

Array3D = NDArray[Literal["* frames, 3 xyz"], np.float64]
NArray3D = NDArray[Literal["* frames, * n, 3 xyz"], np.float64]

# Forceplate-specific
Origin = NDArray[Literal["3 xyz"], np.float64]
NOrigins = NDArray[Literal["3 xyz, n forceplates"], np.float64]

Corners = NDArray[Literal["4 corners, 3 xyz"], np.float64]
NCorners = NDArray[Literal["4 corners, n forceplates, 3 xyz"], np.float64]

CalMatrix = NDArray[Literal["6 rows, 6 columns"], np.float64]
NCalMatrix = NDArray[Literal["6 rows, n forceplates, 6 columns"], np.float64]
