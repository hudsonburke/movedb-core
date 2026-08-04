"""Subject-level metadata extracted from b3d files."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SubjectMetadata(BaseModel):
    """Demographic and model-level metadata for one AddBiomechanics subject.

    This is a read-only descriptor extracted from a ``*.b3d`` file.
    It does *not* contain trial-level signal data; use the other core
    models for per-trial kinematics, GRF, markers, etc.
    """

    source_file: str = Field(description="Path to the source b3d file")
    subject_tags: list[str] = Field(
        default_factory=list, description="Platform tags (e.g. 'healthy')"
    )

    # Demographics
    mass_kg: float = Field(default=0.0, description="Subject mass in kilograms")
    height_m: float = Field(default=0.0, description="Subject height in meters")
    age_years: int = Field(default=0, description="Subject age in years")
    biological_sex: str = Field(
        default="unknown", description="One of 'male', 'female', or 'unknown'"
    )
    notes: str = Field(default="", description="Uploader notes")

    # Data provenance
    href: str = Field(
        default="", description="AddBiomechanics URL for this subject"
    )
    quality: str = Field(
        default="unknown", description="Data quality enum value"
    )

    # Skeleton model
    num_dofs: int = Field(default=0, description="Total DOFs in the skeleton")
    dof_names: list[str] = Field(
        default_factory=list,
        description="Ordered DOF names matching kinematics column order",
    )
    body_names: list[str] = Field(
        default_factory=list,
        description="Body (segment) names in the skeleton",
    )
    ground_force_bodies: list[str] = Field(
        default_factory=list,
        description="Bodies assumed able to take ground-reaction force",
    )

    # Trials
    num_trials: int = Field(default=0)
    num_processing_passes: int = Field(default=0)
    processing_pass_types: list[str] = Field(
        default_factory=list,
        description="Processing pass type names, ordered by pass index",
    )
    trial_names: list[str] = Field(
        default_factory=list,
        description="Trial names in trial-index order",
    )
    trial_lengths: list[int] = Field(
        default_factory=list,
        description="Frame counts per trial, in trial-index order",
    )
    trial_timesteps: list[float] = Field(
        default_factory=list,
        description="Seconds per frame per trial, in trial-index order",
    )

    # Raw OpenSim model XML (optional — large)
    opensim_xml: str | None = Field(
        default=None,
        description="Full OpenSim model XML text from the b3d file",
    )

    # Extra payload for forward compatibility
    extras: dict[str, Any] = Field(
        default_factory=dict,
        description="Unrecognised or forward-compat fields",
    )
