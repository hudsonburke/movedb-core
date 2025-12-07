import numpy as np
from typing import Annotated
from functools import partial
from numpy.typing import NDArray
from pydantic import (
    BaseModel,
    Field,
    model_validator,
    PositiveFloat,
    ConfigDict,
    field_validator,
    AfterValidator,
)


def shape_validator(value: NDArray, expected_shape: tuple[int, ...]):
    """Generate a validator to check array shapes."""
    if value.shape != expected_shape:
        raise ValueError(
            f"Array must have shape {expected_shape}. Got shape {value.shape}"
        )
    return value


Origin = Annotated[
    NDArray[np.float32], AfterValidator(partial(shape_validator, expected_shape=(3,)))
]
Corners = Annotated[
    NDArray[np.float32], AfterValidator(partial(shape_validator, expected_shape=(4, 3)))
]
CalMatrix = Annotated[
    NDArray[np.float32], AfterValidator(partial(shape_validator, expected_shape=(6, 6)))
]


class ForceplateData(BaseModel):
    """Force plate data structure."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    forces: NDArray[np.float32] = Field(
        description="Force vectors array of shape (n_frames, 3) - xyz components"
    )
    moments: NDArray[np.float32] = Field(
        description="Moment vectors array of shape (n_frames, 3) - xyz components"
    )
    cop: NDArray[np.float32] = Field(
        description="Center of pressure array of shape (n_frames, 3) - xyz coordinates"
    )
    cal_matrix: CalMatrix = Field(description="Calibration matrix of shape (6, 6)")
    corners: Corners = Field(
        description="Corner coordinates of shape (4, 3) - xyz for each corner"
    )
    origin: Origin = Field(description="Origin coordinates of shape (3,) - xyz")
    rate: PositiveFloat = Field(description="Sampling rate in Hz")
    unit_force: str = Field(description="Force units (e.g., 'N')", default="N")
    unit_moment: str = Field(description="Moment units (e.g., 'Nm')", default="Nm")
    unit_position: str = Field(
        description="Position units (e.g., 'm', 'mm')", default="m"
    )

    @field_validator("forces", "moments", "cop")
    def check_forceplate_arrays(cls, v: NDArray[np.float32]) -> NDArray[np.float32]:
        if v.ndim != 2:
            raise ValueError(
                f"Force plate data arrays must be 2D (n_frames, 3). Got shape {v.shape}"
            )
        if v.shape[1] != 3:
            raise ValueError(
                f"Force plate data arrays must have 3 components (x, y, z). Got shape {v.shape}"
            )
        return v

    @model_validator(mode="after")
    def check_shapes(self) -> "ForceplateData":
        force_frames, _ = self.forces.shape

        moment_frames, _ = self.moments.shape
        if moment_frames != force_frames:
            raise ValueError(
                f"Moments frames {moment_frames} do not match forces frames {force_frames}."
            )
        cop_frames, _ = self.cop.shape
        if cop_frames != force_frames:
            raise ValueError(
                f"CoP frames {cop_frames} do not match forces frames {force_frames}."
            )
        return self
