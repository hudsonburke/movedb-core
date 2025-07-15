from numpydantic import NDArray, Shape

Vector3D = NDArray[Shape["3"], float]  # pyright: ignore[reportInvalidTypeArguments]

Matrix6x6 = NDArray[Shape["6, 6"], float]  # pyright: ignore[reportInvalidTypeArguments]
Corners3x4 = NDArray[Shape["3, 4"], float]  # pyright: ignore[reportInvalidTypeArguments]


# General matrix types
MatrixNx3 = NDArray[Shape["*, 3"], float]  # pyright: ignore[reportInvalidTypeArguments]
Matrix3x3 = NDArray[Shape["3, 3"], float]  # pyright: ignore[reportInvalidTypeArguments]
Matrix3xN = NDArray[Shape["3, *"], float]  # pyright: ignore[reportInvalidTypeArguments]

CartesianTrajectory = NDArray[Shape["*, 3 xyz"], float]  # pyright: ignore[reportInvalidTypeArguments]