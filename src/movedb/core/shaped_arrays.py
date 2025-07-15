from numpydantic import NDArray, Shape

Vector3D = NDArray[Shape["3"]]  # pyright: ignore[reportInvalidTypeArguments]

Matrix6x6 = NDArray[Shape["6, 6"]]  # pyright: ignore[reportInvalidTypeArguments]
Corners3x4 = NDArray[Shape["3, 4"]]  # pyright: ignore[reportInvalidTypeArguments]


# General matrix types
MatrixNx3 = NDArray[Shape["*, 3"]]  # pyright: ignore[reportInvalidTypeArguments]
Matrix3x3 = NDArray[Shape["3, 3"]]  # pyright: ignore[reportInvalidTypeArguments]
Matrix3xN = NDArray[Shape["3, *"]]  # pyright: ignore[reportInvalidTypeArguments]

CartesianTrajectory = NDArray[
    Shape["*, 3 xyz"]
]  # pyright: ignore[reportInvalidTypeArguments]
