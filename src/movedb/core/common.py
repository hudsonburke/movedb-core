import numpy as np
from pydantic import PositiveInt, PositiveFloat
from numpydantic import NDArray
from typing import Literal
from dataclasses import dataclass


@dataclass
class Vec3:
    x: float
    y: float
    z: float


@dataclass
class Vec3Array: ...


SingleMarkerArray = NDArray[Literal["* frames, 3 xyz"], np.float64]
MarkerArray = NDArray[Literal["* frames, * markers, 3 xyz"], np.float64]
ResidualsArray = NDArray[Literal["* frames, * markers"], np.float64]
SingleResidualsArray = NDArray[Literal["* frames"], np.float64]
TimeVector = NDArray[Literal["* frames"], np.float64]

AnalogArray = NDArray[Literal["* frames, * channels"], np.float64]
Array1D = NDArray[Literal["* frames"], np.float64]

Array3D = NDArray[Literal["* frames, 3 xyz"], np.float64]

Origin = NDArray[Literal["3 xyz"], np.float64]
Corners = NDArray[Literal["4 corners, 3 xyz"], np.float64]
CalMatrix = NDArray[Literal["6 rows, 6 columns"], np.float64]

Rate = PositiveFloat
Frame = PositiveInt
