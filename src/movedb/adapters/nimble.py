"""Extract typed biomechanics models from NimblePhysics/AddBiomechanics b3d files.

Uses ``nimblephysics.biomechanics.SubjectOnDisk`` to lazily read and convert
b3d data into ``movedb.core`` Pydantic models ready for storage and analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ..core import (
    ForceplateData,
    GRFData,
    KinematicsData,
    MarkerData,
    SubjectMetadata,
    TrialData,
)

if TYPE_CHECKING:
    import nimblephysics as nimble


# ---------------------------------------------------------------------------
# Subject-level metadata
# ---------------------------------------------------------------------------


def extract_subject_metadata(subject: nimble.biomechanics.SubjectOnDisk) -> SubjectMetadata:
    """Extract subject-level metadata from a b3d file.

    This reads demographics, skeleton structure, and trial inventory
    without loading any frame data.  Safe to call on many files.
    """

    num_trials = subject.getNumTrials()
    num_passes = subject.getNumProcessingPasses()

    pass_types: list[str] = []
    for p in range(num_passes):
        pt = subject.getProcessingPassType(p)
        pass_types.append(str(pt).split(".")[-1] if "." in str(pt) else str(pt))

    trial_names: list[str] = []
    trial_lengths: list[int] = []
    trial_timesteps: list[float] = []
    for t in range(num_trials):
        trial_names.append(subject.getTrialName(t))
        trial_lengths.append(subject.getTrialLength(t))
        trial_timesteps.append(subject.getTrialTimestep(t))

    # Skeleton info — readSkel is lightweight (no geometry loaded)
    skel = subject.readSkel(processingPass=0, ignoreGeometry=True)
    dof_names = [skel.getDofByIndex(i).getName() for i in range(skel.getNumDofs())]
    body_names = [skel.getBodyNode(i).getName() for i in range(skel.getNumBodyNodes())]

    return SubjectMetadata(
        source_file="",
        subject_tags=list(subject.getSubjectTags()),
        mass_kg=subject.getMassKg(),
        height_m=subject.getHeightM(),
        age_years=subject.getAgeYears(),
        biological_sex=subject.getBiologicalSex(),
        notes=subject.getNotes(),
        href=subject.getHref(),
        quality=str(subject.getQuality()).split(".")[-1]
        if "." in str(subject.getQuality())
        else str(subject.getQuality()),
        num_dofs=subject.getNumDofs(),
        dof_names=dof_names,
        body_names=body_names,
        ground_force_bodies=list(subject.getGroundForceBodies()),
        num_trials=num_trials,
        num_processing_passes=num_passes,
        processing_pass_types=pass_types,
        trial_names=trial_names,
        trial_lengths=trial_lengths,
        trial_timesteps=trial_timesteps,
    )


# ---------------------------------------------------------------------------
# Trial-level signal extractors
# ---------------------------------------------------------------------------


def extract_kinematics(
    subject: nimble.biomechanics.SubjectOnDisk,
    trial: int,
    processing_pass: int = 0,
    *,
    start_frame: int = 0,
    num_frames: int | None = None,
) -> KinematicsData:
    """Extract joint kinematics for one trial and processing pass.

    Parameters
    ----------
    processing_pass:
        Pass index (0 = kinematics, 1 = low-pass, 2 = dynamics).
    start_frame, num_frames:
        Slice the trial.  ``num_frames=None`` reads to the end.
    """

    trial_len = subject.getTrialLength(trial)
    if num_frames is None:
        num_frames = trial_len - start_frame
    effective = min(num_frames, trial_len - start_frame)

    dt = subject.getTrialTimestep(trial)
    rate = 1.0 / dt
    n_dofs = subject.getNumDofs()

    # Skeleton for DOF / body names
    skel = subject.readSkel(processingPass=processing_pass, ignoreGeometry=True)
    dof_names = [skel.getDofByIndex(i).getName() for i in range(n_dofs)]
    body_names = [skel.getBodyNode(i).getName() for i in range(skel.getNumBodyNodes())]

    # Pass type string
    pt = subject.getProcessingPassType(processing_pass)
    pass_type_str = str(pt).split(".")[-1] if "." in str(pt) else str(pt)

    # Read frames in one batch
    frames = subject.readFrames(
        trial=trial,
        startFrame=start_frame,
        numFramesToRead=effective,
        includeSensorData=False,
        includeProcessingPasses=True,
    )

    # Allocate
    pos = np.empty((effective, n_dofs), dtype=np.float64)
    vel = np.empty((effective, n_dofs), dtype=np.float64)
    acc = np.empty((effective, n_dofs), dtype=np.float64)
    tau = np.empty((effective, n_dofs), dtype=np.float64)
    pos_obs = np.empty((effective, n_dofs), dtype=np.float64)
    vel_fd = np.empty((effective, n_dofs), dtype=np.float64)
    acc_fd = np.empty((effective, n_dofs), dtype=np.float64)

    for i, frame in enumerate(frames):
        pp = frame.processingPasses[processing_pass]
        pos[i] = pp.pos
        vel[i] = pp.vel
        acc[i] = pp.acc
        tau[i] = pp.tau
        pos_obs[i] = pp.posObserved
        vel_fd[i] = pp.velFiniteDifferenced
        acc_fd[i] = pp.accFiniteDifferenced

    return KinematicsData(
        rate=rate,
        first_frame=start_frame + 1,
        names=dof_names,
        body_names=body_names,
        processing_pass_type=pass_type_str,
        pos=pos,
        vel=vel,
        acc=acc,
        tau=tau,
        pos_observed=pos_obs,
        vel_finite_differenced=vel_fd,
        acc_finite_differenced=acc_fd,
    )


def extract_grf(
    subject: nimble.biomechanics.SubjectOnDisk,
    trial: int,
    processing_pass: int = 2,
    *,
    start_frame: int = 0,
    num_frames: int | None = None,
) -> GRFData:
    """Extract ground reaction forces for one trial and processing pass.

    Defaults to the *dynamics* pass (index 2) because GRF data is
    only physically meaningful after dynamics optimisation.
    """

    trial_len = subject.getTrialLength(trial)
    if num_frames is None:
        num_frames = trial_len - start_frame
    effective = min(num_frames, trial_len - start_frame)

    dt = subject.getTrialTimestep(trial)
    rate = 1.0 / dt

    body_names = list(subject.getGroundForceBodies())
    if not body_names:
        raise ValueError(f"No ground-force bodies found for trial {trial}")

    n_bodies = len(body_names)

    pt = subject.getProcessingPassType(processing_pass)
    pass_type_str = str(pt).split(".")[-1] if "." in str(pt) else str(pt)

    frames = subject.readFrames(
        trial=trial,
        startFrame=start_frame,
        numFramesToRead=effective,
        includeSensorData=False,
        includeProcessingPasses=True,
    )

    force = np.empty((effective, n_bodies, 3), dtype=np.float64)
    cop = np.empty((effective, n_bodies, 3), dtype=np.float64)
    torque = np.empty((effective, n_bodies, 3), dtype=np.float64)
    force_root = np.empty((effective, n_bodies, 3), dtype=np.float64)
    cop_root = np.empty((effective, n_bodies, 3), dtype=np.float64)
    torque_root = np.empty((effective, n_bodies, 3), dtype=np.float64)
    contact = np.empty((effective, n_bodies), dtype=np.float64)

    for i, frame in enumerate(frames):
        pp = frame.processingPasses[processing_pass]
        force[i] = pp.groundContactForce.reshape(n_bodies, 3)
        cop[i] = pp.groundContactCenterOfPressure.reshape(n_bodies, 3)
        torque[i] = pp.groundContactTorque.reshape(n_bodies, 3)
        force_root[i] = pp.groundContactForceInRootFrame.reshape(n_bodies, 3)
        cop_root[i] = pp.groundContactCenterOfPressureInRootFrame.reshape(n_bodies, 3)
        torque_root[i] = pp.groundContactTorqueInRootFrame.reshape(n_bodies, 3)
        contact[i] = pp.contact

    return GRFData(
        rate=rate,
        first_frame=start_frame + 1,
        names=body_names,
        processing_pass_type=pass_type_str,
        force=force,
        cop=cop,
        torque=torque,
        force_root=force_root,
        cop_root=cop_root,
        torque_root=torque_root,
        contact=contact,
    )


def extract_markers(
    subject: nimble.biomechanics.SubjectOnDisk,
    trial: int,
    *,
    start_frame: int = 0,
    num_frames: int | None = None,
) -> MarkerData:
    """Extract marker trajectories for one trial.

    Marker observations can be sparse (some markers missing on some
    frames).  Missing observations are filled with ``NaN`` and the
    ``residuals`` array carries a 1/0 mask tracking which frames each
    marker was observed.
    """

    trial_len = subject.getTrialLength(trial)
    if num_frames is None:
        num_frames = trial_len - start_frame
    effective = min(num_frames, trial_len - start_frame)

    dt = subject.getTrialTimestep(trial)
    rate = 1.0 / dt

    # Discover the full marker set by scanning frame observations.
    # We read a small sample first to learn the marker names, then
    # read the full batch.  This avoids a separate OpenSim dependency
    # and captures all markers actually present in the data.
    probe_frames = subject.readFrames(
        trial=trial,
        startFrame=start_frame,
        numFramesToRead=min(effective, 50),
        includeSensorData=True,
        includeProcessingPasses=False,
    )
    all_marker_names_set: set[str] = set()
    for f in probe_frames:
        for name, _pos in f.markerObservations:
            all_marker_names_set.add(name)
    # Sort for deterministic column order
    all_marker_names = sorted(all_marker_names_set)
    n_markers = len(all_marker_names)
    name_to_idx = {name: idx for idx, name in enumerate(all_marker_names)}

    # Read the full frame batch
    frames = subject.readFrames(
        trial=trial,
        startFrame=start_frame,
        numFramesToRead=effective,
        includeSensorData=True,
        includeProcessingPasses=False,
    )

    data = np.full((effective, n_markers, 3), np.nan, dtype=np.float64)
    residuals = np.zeros((effective, n_markers), dtype=np.float64)

    for i, frame in enumerate(frames):
        for name, pos in frame.markerObservations:
            idx = name_to_idx.get(name)
            if idx is not None:
                data[i, idx] = pos
                residuals[i, idx] = 1.0

    return MarkerData(
        rate=rate,
        first_frame=start_frame + 1,
        names=all_marker_names,
        units="m",
        data=data,
        residuals=residuals,
    )


def extract_forceplates(
    subject: nimble.biomechanics.SubjectOnDisk,
    trial: int,
    *,
    start_frame: int = 0,
    num_frames: int | None = None,
) -> ForceplateData | None:
    """Extract raw force plate readings for one trial.

    Returns ``None`` if the trial has no force plates.
    """

    n_plates = subject.getNumForcePlates(trial)
    if n_plates == 0:
        return None

    trial_len = subject.getTrialLength(trial)
    if num_frames is None:
        num_frames = trial_len - start_frame
    effective = min(num_frames, trial_len - start_frame)

    dt = subject.getTrialTimestep(trial)
    rate = 1.0 / dt

    # Get force plate names — use indices as names if unavailable
    fp_names = [f"FP{i + 1}" for i in range(n_plates)]

    # Get force plate geometry
    origins_list: list[np.ndarray] = []
    corners_list: list[np.ndarray] = []
    for fp in range(n_plates):
        raw_corners = subject.getForcePlateCorners(trial, fp)
        if len(raw_corners) > 0:
            corners_list.append(np.array(raw_corners))  # (4, 3)
        else:
            corners_list.append(np.zeros((4, 3)))
        # Origin is typically the first corner
        origins_list.append(corners_list[-1][0] if corners_list[-1].size > 0 else np.zeros(3))

    origins = np.column_stack(origins_list)  # (3, n_plates)
    corners = np.stack(corners_list, axis=1)  # (4, n_plates, 3)

    # Calibration matrices — identity when not available
    cal_matrices = np.tile(np.eye(6), (n_plates, 1, 1)).transpose(1, 0, 2)  # (6, n_plates, 6)

    # Read frames
    frames = subject.readFrames(
        trial=trial,
        startFrame=start_frame,
        numFramesToRead=effective,
        includeSensorData=True,
        includeProcessingPasses=False,
    )

    forces = np.empty((effective, n_plates, 3), dtype=np.float64)
    moments = np.empty((effective, n_plates, 3), dtype=np.float64)
    cop = np.empty((effective, n_plates, 3), dtype=np.float64)

    for i, frame in enumerate(frames):
        for fp in range(n_plates):
            if fp < len(frame.rawForcePlateForces):
                forces[i, fp] = frame.rawForcePlateForces[fp]
            else:
                forces[i, fp] = np.nan
            if fp < len(frame.rawForcePlateTorques):
                moments[i, fp] = frame.rawForcePlateTorques[fp]
            else:
                moments[i, fp] = np.nan
            if fp < len(frame.rawForcePlateCenterOfPressures):
                cop[i, fp] = frame.rawForcePlateCenterOfPressures[fp]
            else:
                cop[i, fp] = np.nan

    return ForceplateData(
        rate=rate,
        first_frame=start_frame + 1,
        names=fp_names,
        units_force=["N"] * n_plates,
        units_moment=["Nmm"] * n_plates,
        units_position=["mm"] * n_plates,
        origins=origins,
        corners=corners,
        cal_matrices=cal_matrices,
        forces=forces,
        moments=moments,
        cop=cop,
    )


# ---------------------------------------------------------------------------
# High-level trial extraction
# ---------------------------------------------------------------------------


def extract_trial(
    subject: nimble.biomechanics.SubjectOnDisk,
    trial: int,
    processing_pass: int = 0,
    *,
    start_frame: int = 0,
    num_frames: int | None = None,
    include_grf: bool = True,
) -> TrialData:
    """Extract a complete ``TrialData`` for one trial and processing pass.

    Parameters
    ----------
    processing_pass:
        Which processing pass to use for kinematics and GRF data.
    include_grf:
        If True (default), also extract GRF data.  GRF is only
        meaningful from the dynamics pass (index 2).  Set to False
        when extracting from kinematics-only passes.
    """

    name = subject.getTrialName(trial)
    kinematics = extract_kinematics(
        subject, trial, processing_pass,
        start_frame=start_frame, num_frames=num_frames,
    )
    grf = None
    if include_grf:
        try:
            grf = extract_grf(
                subject, trial, processing_pass,
                start_frame=start_frame, num_frames=num_frames,
            )
        except (ValueError, IndexError):
            pass

    markers = extract_markers(
        subject, trial,
        start_frame=start_frame, num_frames=num_frames,
    )
    forceplates = extract_forceplates(
        subject, trial,
        start_frame=start_frame, num_frames=num_frames,
    )

    return TrialData(
        name=name,
        markers=markers,
        forceplates=forceplates,
        kinematics=kinematics,
        grf=grf,
    )


def extract_all_trials(
    subject: nimble.biomechanics.SubjectOnDisk,
    processing_pass: int = 0,
    *,
    include_grf: bool = True,
) -> list[TrialData]:
    """Extract every trial from a b3d file.

    Returns a list of ``TrialData``, one per trial, in trial-index order.
    """

    trials: list[TrialData] = []
    for t in range(subject.getNumTrials()):
        td = extract_trial(subject, t, processing_pass, include_grf=include_grf)
        trials.append(td)
    return trials
