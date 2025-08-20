import ezc3d
import numpy as np
from typing import Any
from .models import Trial, Event, Analog, Marker, ForcePlate

def get_c3d_param(
    c3d_object: ezc3d.c3d, *keys, index: int | None = None, default=None
) -> Any:
    """
    Helper function to get nested parameters from a C3D object.
    """
    param: dict = c3d_object.parameters
    for key in keys:
        param = param.get(key, {})
    value = param.get("value", {})
    if index is not None and (isinstance(value, list) or isinstance(value, np.ndarray)):
        if index < 0 or index >= len(value):
            raise IndexError(f"Index {index} out of range for parameter '{keys}'.")
        return value[index]
    return value if value is not None else default

def event_from_c3d(c3d_obj: ezc3d.c3d, index: int = 0) -> Event:
    if not "EVENT" in c3d_obj.parameters:
        raise ValueError("C3D object does not contain EVENT parameters.")
    context = get_c3d_param(c3d_obj, "EVENT", "CONTEXTS", index=index, default="")
    label = get_c3d_param(c3d_obj, "EVENT", "LABELS", index=index, default="")
    # Get time in seconds from (min, sec) format
    time_min, time_sec=  get_c3d_param(
        c3d_obj, "EVENT", "TIMES", default=[[None, None]]
    )[:, index]
    if time_min is None or time_sec is None:
        raise ValueError(
            f"Invalid time data for event at index {index} in C3D object"
        )
    description = get_c3d_param(
        c3d_obj, "EVENT", "DESCRIPTIONS", index=index, default=""
    )
    event = Event(
        context=context,
        label=label,
        time=time_min * 60 + time_sec,  # Convert from (min, sec) to sec
        description=description,
    )

def fp_from_c3d(c3d_obj: ezc3d.c3d, index: int = 0) -> ForcePlate:
    if not "platform" in c3d_obj.data:
        raise ValueError(
            "C3D object does not contain ezc3d platform data. Make sure to set the extract_forceplat_data=True in ezc3d.c3d constructor."
        )
    c3d_fp = c3d_obj.data["platform"]
    if index >= len(c3d_fp):
        raise IndexError(
            f"Index {index} out of range for force platforms. Available: {len(c3d_fp)}"
        )
    fp: dict = c3d_fp[index]
    force = fp.get("force", np.zeros((3, 0)))
    n_frames = force.shape[1]

    moment = fp.get("moment", np.zeros((3, n_frames)))
    position = fp.get("center_of_pressure", np.zeros((3, n_frames)))
    free_moment = fp.get("Tz", np.zeros((3, n_frames)))
    
    ezfp = EZForcePlatform(
        unit_force=fp.get("unit_force", "N"),
        unit_moment=fp.get("unit_moment", "Nm"),
        unit_position=fp.get("unit_position", "m"),
        cal_matrix=fp.get("cal_matrix", np.eye(6)),
        corners=fp.get("corners", np.zeros((4, 3))),
        origin=fp.get("origin", np.zeros(3)),
        data=(force, moment, position, free_moment)
    )

def marker_from_c3d(c3d_object: ezc3d.c3d, index: int = 0) -> Marker:
    description = get_c3d_param(
        c3d_object,
        "POINT",
        "DESCRIPTIONS",
        index=index,
        default=MarkerTrajectory.model_fields["description"].default,
    )
    marker = MarkerTrajectory(
        data=DataFrame[MarkerSchema](
            {
                "x": c3d_object.data["points"][0, index, :].tolist(),
                "y": c3d_object.data["points"][1, index, :].tolist(),
                "z": c3d_object.data["points"][2, index, :].tolist(),
                "residual": c3d_object.data["meta_points"]["residuals"][
                    0, index, :
                ].tolist(),
            }
        ),
        description=description,
    )
    return marker

def points_from_c3d(c3d_object: ezc3d.c3d) -> :
    if not "POINT" in c3d_object.parameters:
        raise ValueError("C3D object does not contain POINT parameters.")
    if not "points" in c3d_object.data:
        raise ValueError("C3D object does not contain point data.")
    header_first_frame = c3d_object.header["points"]["first_frame"]
    header_last_frame = c3d_object.header["points"]["last_frame"]
    header_rate = c3d_object.header["points"]["frame_rate"]

    camera_rate = get_c3d_param(
        c3d_object, "TRIAL", "CAMERA_RATE", default=header_rate
    )
    point_rate = get_c3d_param(c3d_object, "POINT", "RATE", default=camera_rate)
    if camera_rate != header_rate:
        logger.warning(
            f"Camera rate {camera_rate} does not match header rate {header_rate}. Defaulting to camera rate."
        )
    if point_rate != camera_rate:
        logger.warning(
            f"Point rate {point_rate} does not match camera rate {camera_rate}. Defaulting to point rate."
        )

    labels = get_c3d_param(c3d_object, "POINT", "LABELS", default=[])
    units = get_c3d_param(
        c3d_object, "POINT", "UNITS", default=[Points.model_fields["units"].default]
    )[0]

    return Points(
        first_frame=header_first_frame,
        last_frame=header_last_frame,
        rate=point_rate,
        units=units,
        trajectories={
            label: MarkerTrajectory.from_c3d(c3d_object, index=i)
            for i, label in enumerate(labels)
        },
    )

def analog_from_c3d(c3d_obj: ezc3d.c3d, index: int = 0) -> Analog:
    analog_data = c3d_obj.data["analogs"][0, index, :].tolist()
    units = get_c3d_param(
        c3d_obj,
        "ANALOG",
        "UNITS",
        index=index,
        default=cls.model_fields["units"].default,
    )
    scale = get_c3d_param(
        c3d_obj,
        "ANALOG",
        "SCALE",
        index=index,
        default=cls.model_fields["scale"].default,
    )
    offset = get_c3d_param(
        c3d_obj,
        "ANALOG",
        "OFFSET",
        index=index,
        default=cls.model_fields["offset"].default,
    )
    description = get_c3d_param(
        c3d_obj,
        "ANALOG",
        "DESCRIPTIONS",
        index=index,
        default=cls.model_fields["description"].default,
    )

    return cls(
        data=analog_data,
        units=units,
        scale=scale,
        offset=offset,
        description=description,
    )

def analogs_from_c3d(c3d_object: ezc3d.c3d) -> Analogs:
    if not "ANALOG" in c3d_object.parameters:
        raise ValueError("C3D object does not contain ANALOG parameters.")
    if not "analogs" in c3d_object.data:
        raise ValueError("C3D object does not contain analog data.")

    header_first_frame = c3d_object.header["analogs"]["first_frame"]
    header_last_frame = c3d_object.header["analogs"]["last_frame"]
    header_rate = c3d_object.header["analogs"]["frame_rate"]

    analog_rate = get_c3d_param(c3d_object, "ANALOG", "RATE", default=header_rate)
    if analog_rate != header_rate:
        logger.warning(
            f"Analog rate {analog_rate} does not match header rate {header_rate}. Defaulting to analog rate."
        )

    labels = get_c3d_param(c3d_object, "ANALOG", "LABELS", default=[])

    gen_scale = get_c3d_param(c3d_object, "ANALOG", "GEN_SCALE", default=[1.0])[0]

    return cls(
        first_frame=header_first_frame,  # TODO: Maybe ignore header and set this based on data?
        last_frame=header_last_frame,
        rate=analog_rate,
        gen_scale=gen_scale,
        channels={
            label: AnalogChannel.from_c3d(c3d_object, index=i)
            for i, label in enumerate(labels)
        },
    )
