import numpy as np
from numpydantic import NDArray
from typing import Literal  # Better for static type checking than numpydantic.Shape

# Common
Array1D = NDArray[Literal["* frames"], np.float64]
NArray1D = NDArray[Literal["* frames, * n"], np.float64]
# (n_frames, n_channels) — scalar per channel per frame (kinematics, masks)
NArray2D = NArray1D  # semantic alias: n_frames × n_channels

# Boolean mask arrays stored as float64 (from nimblephysics)
NArrayMask = NDArray[Literal["* frames, * n"], np.float64]

Array3D = NDArray[Literal["* frames, 3 xyz"], np.float64]
NArray3D = NDArray[Literal["* frames, * n, 3 xyz"], np.float64]


# Forceplate-specific
Origin = NDArray[Literal["3 xyz"], np.float64]
NOrigins = NDArray[Literal["3 xyz, * forceplates"], np.float64]

Corners = NDArray[Literal["4 corners, 3 xyz"], np.float64]
NCorners = NDArray[Literal["4 corners, * forceplates, 3 xyz"], np.float64]

CalMatrix = NDArray[Literal["6 rows, 6 columns"], np.float64]
NCalMatrix = NDArray[Literal["6 rows, * forceplates, 6 columns"], np.float64]
