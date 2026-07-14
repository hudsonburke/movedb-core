"""Ground reaction force data from b3d processing passes."""

import numpy as np
from functools import cached_property
from typing import Literal, Self

from pydantic import Field, model_validator

from .metadata import _MetaBase
from .shapes import NArray3D, NArrayMask, Array1D


class GRFMeta(_MetaBase):
    """Metadata for ground reaction force data.

    ``names`` holds the contact body names (e.g. ``["calcn_r", "calcn_l"]``),
    one per body that was assumed able to take ground-reaction force.
    """

    type: Literal["grf"] = "grf"
    units_force: str = Field(default="N", description="Force units")
    units_torque: str = Field(default="Nm", description="Torque units")
    units_position: str = Field(default="m", description="Position units")
    processing_pass_type: str = Field(
        default="dynamics",
        description="Processing pass: kinematics, dynamics, or low_pass_filter",
    )


class GRFData(GRFMeta):
    """Ground reaction forces, torques, and centres of pressure per contact body.

    World-frame arrays have shape ``(n_frames, n_bodies, 3)``.
    Root-frame variants (when available) are expressed in the root body's
    local coordinate frame (typically the pelvis).

    ``names`` (inherited from ``_MetaBase``) gives the contact body names
    in column order.
    """

    force: NArray3D = Field(
        description="Ground reaction force in world frame; "
        "shape (n_frames, n_bodies, 3)"
    )
    cop: NArray3D = Field(
        description="Centre of pressure in world frame; "
        "shape (n_frames, n_bodies, 3)"
    )
    torque: NArray3D = Field(
        description="Ground reaction torque in world frame; "
        "shape (n_frames, n_bodies, 3)"
    )
    force_root: NArray3D | None = Field(
        default=None,
        description="Ground reaction force in root-body frame; "
        "shape (n_frames, n_bodies, 3)",
    )
    cop_root: NArray3D | None = Field(
        default=None,
        description="Centre of pressure in root-body frame; "
        "shape (n_frames, n_bodies, 3)",
    )
    torque_root: NArray3D | None = Field(
        default=None,
        description="Ground reaction torque in root-body frame; "
        "shape (n_frames, n_bodies, 3)",
    )
    contact: NArrayMask | None = Field(
        default=None,
        description="Boolean float mask of shape (n_frames, n_bodies); "
        "1.0 = body is in contact with the ground on this frame",
    )

    @cached_property
    def num_frames(self) -> int:
        return np.asarray(self.force).shape[0]

    @cached_property
    def time_vector(self) -> Array1D:
        return np.arange(self.num_frames) / self.rate

    @model_validator(mode="after")
    def check_shapes(self) -> Self:
        force_np = np.asarray(self.force)
        n_frames, n_bodies, _ = force_np.shape

        if len(self.names) != n_bodies:
            raise ValueError(
                f"Mismatch: {len(self.names)} body names provided, "
                f"but force array has {n_bodies} bodies."
            )

        for name, arr in [
            ("cop", self.cop),
            ("torque", self.torque),
        ]:
            arr_np = np.asarray(arr)
            if arr_np.shape != (n_frames, n_bodies, 3):
                raise ValueError(
                    f"Shape mismatch: force {force_np.shape} vs {name} {arr_np.shape}"
                )

        for name, arr in [
            ("force_root", self.force_root),
            ("cop_root", self.cop_root),
            ("torque_root", self.torque_root),
        ]:
            if arr is None:
                continue
            arr_np = np.asarray(arr)
            if arr_np.shape != (n_frames, n_bodies, 3):
                raise ValueError(
                    f"Shape mismatch: force {force_np.shape} vs {name} {arr_np.shape}"
                )

        if self.contact is not None:
            contact_np = np.asarray(self.contact)
            if contact_np.shape != (n_frames, n_bodies):
                raise ValueError(
                    f"Shape mismatch: force {force_np.shape} vs "
                    f"contact {contact_np.shape}"
                )

        return self
