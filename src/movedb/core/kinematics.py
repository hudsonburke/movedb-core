"""Joint kinematics data from b3d processing passes."""

import numpy as np
from functools import cached_property
from typing import Literal, Self

from pydantic import Field, model_validator

from .metadata import _MetaBase
from .shapes import NArray2D, NArrayMask, Array1D


class KinematicsMeta(_MetaBase):
    """Metadata for joint kinematics, embedded in Parquet file-level metadata."""

    type: Literal["kinematics"] = "kinematics"
    units: str = Field(default="rad", description="Angular units for joint DOFs")
    body_names: list[str] = Field(
        description="Body (segment) names in the skeleton"
    )
    processing_pass_type: str = Field(
        default="kinematics",
        description="Processing pass: kinematics, dynamics, or low_pass_filter",
    )


class KinematicsData(KinematicsMeta):
    """Joint kinematics for a single trial and processing pass.

    Each array has shape ``(n_frames, n_dofs)`` where DOF order matches
    ``names`` (inherited from ``_MetaBase``).
    """

    pos: NArray2D = Field(
        description="Joint positions array of shape (n_frames, n_dofs)"
    )
    vel: NArray2D = Field(
        description="Joint velocities array of shape (n_frames, n_dofs)"
    )
    acc: NArray2D = Field(
        description="Joint accelerations array of shape (n_frames, n_dofs)"
    )
    tau: NArray2D = Field(
        description="Joint torques (control forces) array of shape (n_frames, n_dofs)"
    )
    pos_observed: NArrayMask | None = Field(
        default=None,
        description="Boolean float mask of shape (n_frames, n_dofs); "
        "1.0 = DOF position was directly observed on this frame",
    )
    vel_finite_differenced: NArrayMask | None = Field(
        default=None,
        description="Boolean float mask of shape (n_frames, n_dofs); "
        "1.0 = DOF velocity was finite-differenced (less reliable)",
    )
    acc_finite_differenced: NArrayMask | None = Field(
        default=None,
        description="Boolean float mask of shape (n_frames, n_dofs); "
        "1.0 = DOF acceleration was finite-differenced (less reliable)",
    )

    @cached_property
    def num_frames(self) -> int:
        return np.asarray(self.pos).shape[0]

    @cached_property
    def time_vector(self) -> Array1D:
        return np.arange(self.num_frames) / self.rate

    @model_validator(mode="after")
    def check_shapes(self) -> Self:
        pos = np.asarray(self.pos)
        n_frames, n_dofs = pos.shape

        if len(self.names) != n_dofs:
            raise ValueError(
                f"Mismatch: {len(self.names)} DOF names provided, "
                f"but pos array has {n_dofs} columns."
            )

        for name, arr in [
            ("vel", self.vel),
            ("acc", self.acc),
            ("tau", self.tau),
        ]:
            arr_np = np.asarray(arr)
            if arr_np.shape != (n_frames, n_dofs):
                raise ValueError(
                    f"Shape mismatch: pos {pos.shape} vs {name} {arr_np.shape}"
                )

        for name, arr in [
            ("pos_observed", self.pos_observed),
            ("vel_finite_differenced", self.vel_finite_differenced),
            ("acc_finite_differenced", self.acc_finite_differenced),
        ]:
            if arr is None:
                continue
            arr_np = np.asarray(arr)
            if arr_np.shape != (n_frames, n_dofs):
                raise ValueError(
                    f"Shape mismatch: pos {pos.shape} vs {name} {arr_np.shape}"
                )

        return self
