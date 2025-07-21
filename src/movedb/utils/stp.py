import numpy as np

from ..core import Trial
from loguru import logger
# NOT YET IMPLEMENTED -- Maybe should be part of Trial class?


# Spatiotemporal parameters  -- Currently following Huxham et al. 2006 for straight line gait
# TODO: Implement Dingwell 2024 calculations
def stride_time(trial: Trial) -> dict[str, list[float]]:
    """ """
    times = {"Left": [], "Right": []}
    for side in ["Left", "Right"]:
        foot_strike = trial.get_events(label="Foot Strike", context=side)
        if not foot_strike:
            logger.warning(f"No foot strike events found for {side} side")
            continue
        foot_strike_times = [event.get_time(trial.points.rate) for event in foot_strike]
        if len(foot_strike_times) < 2:
            logger.warning(
                f"Not enough foot strike events for {side} side to calculate stride time"
            )
            continue
        for i in range(len(foot_strike_times) - 1):
            start_time = foot_strike_times[i]
            end_time = foot_strike_times[i + 1]
            time_diff = end_time - start_time
            times[side].append(time_diff)
    return times


def stride_length(trial: Trial) -> dict[str, list[float]]:
    lengths = {"Left": [], "Right": []}
    for side in ["Left", "Right"]:
        foot_marker = side[0].upper() + "TOE"
        if foot_marker not in trial.points.trajectories:
            logger.warning(f"Marker {foot_marker} not found in trial points")
            continue
        foot_strike = trial.get_events(label="Foot Strike", context=side)
        if not foot_strike:
            logger.warning(f"No foot strike events found for {side} side")
            continue
        foot_strike_frames = [
            event.get_frame(trial.points.rate) for event in foot_strike
        ]
        if len(foot_strike_frames) < 2:
            logger.warning(
                f"Not enough foot strike events for {side} side to calculate stride length"
            )
            continue
        for i in range(len(foot_strike_frames) - 1):
            start_frame = foot_strike_frames[i]
            end_frame = foot_strike_frames[i + 1]
            start_pos = trial.points.get_marker_coords(foot_marker, start_frame)
            end_pos = trial.points.get_marker_coords(foot_marker, end_frame)
            if start_pos is None or end_pos is None:
                logger.warning(
                    f"Missing marker position for {foot_marker} at frames {start_frame} or {end_frame}"
                )
                continue
            length = np.linalg.norm(np.array(end_pos) - np.array(start_pos))
            lengths[side].append(length)
    return lengths


def stride_width(trial: Trial) -> dict[str, list[float]]:
    raise NotImplementedError("Stride width calculation is not implemented yet.")


def stride_velocity(trial: Trial) -> dict[str, list[float]]:
    stride_lengths = stride_length(trial)
    stride_times = stride_time(trial)
    velocities = {"Left": [], "Right": []}

    for side in ["Left", "Right"]:
        lengths = stride_lengths.get(side, [])
        times = stride_times.get(side, [])

        if not lengths or not times:
            logger.warning(
                f"Not enough data to calculate stride velocity for {side} side"
            )
            continue

        # Ensure we have a 1:1 mapping of lengths to times
        # This assumes that stride_length and stride_time will return lists of the same length for a given side
        # and that the i-th length corresponds to the i-th time.
        for i in range(min(len(lengths), len(times))):
            if times[i] == 0:  # Avoid division by zero
                logger.warning(
                    f"Stride time is zero for {side} side, cannot calculate velocity for stride {i}"
                )
                velocities[side].append(float("nan"))  # Or handle as appropriate
            else:
                velocities[side].append(lengths[i] / times[i])

        if len(lengths) != len(times):
            logger.warning(
                f"Mismatch in number of stride lengths and times for {side} side. "
                f"Velocity calculated for {min(len(lengths), len(times))} strides."
            )

    return velocities


def stride_cadence(trial: Trial) -> dict[str, list[float]]:
    """ """
    velocities = stride_velocity(trial)
    cadences = {
        "Left": [1 / vel for vel in velocities.get("Left", []) if vel != 0],
        "Right": [1 / vel for vel in velocities.get("Right", []) if vel != 0],
    }
    return cadences


def step_time(trial: Trial) -> dict[str, list[float]]:
    """
    Step time is calculated as the time from foot strike to next contralateral foot strike
    """
    # TODO: Implement step time calculation
    left_foot_strikes = trial.get_events(label="Foot Strike", context="Left")
    right_foot_strikes = trial.get_events(label="Foot Strike", context="Right")

    # Use the variables to avoid unused variable warnings
    _ = left_foot_strikes
    _ = right_foot_strikes

    times = {"Left": [], "Right": []}
    return times


def step_length(trial):
    """ """
    pass


def step_width(trial) -> list[float]:
    """ """
    widths = []
    return widths


def step_velocity(trial):
    pass


def step_cadence(trial) -> list[float]:
    """ """
    cadences = []
    return cadences


def stance_time(trial) -> dict[str, list[float]]:
    """
    Calculates the stance time for each stride as the time between foot strike and foot off events for one side
    """
    times = {"Left": [], "Right": []}
    for side in ["Left", "Right"]:
        foot_strike = trial.get_events(label="Foot Strike", context=side)
        foot_off = trial.get_events(label="Foot Off", context=side)
        if not foot_strike:
            logger.warning(f"No foot strike events found for {side} side")
            continue
        if not foot_off:
            logger.warning(f"No foot off events found for {side} side")
            continue
        # TODO: Implement stance time calculation
        foot_strike_times = [event.get_time(trial.points.rate) for event in foot_strike]
        foot_off_times = [event.get_time(trial.points.rate) for event in foot_off]

        # Use the variables to avoid unused variable warnings
        _ = foot_strike_times
        _ = foot_off_times

    return times


def stance_percentage(trial) -> dict[str, list[float]]:
    """
    Calculates the percentage of stance time for each stride
    """
    percentages = {"Left": [], "Right": []}
    stance_times = trial.stance_time()
    stride_times = trial.stride_time()
    for side in ["Left", "Right"]:
        stance = stance_times.get(side, [])
        stride = stride_times.get(side, [])
        if not stance or not stride:
            logger.warning(
                f"Not enough data to calculate stance percentage for {side} side"
            )
            continue
        for i in range(min(len(stance), len(stride))):
            if stride[i] == 0:
                logger.warning(
                    f"Stride time is zero for {side} side, cannot calculate stance percentage for stride {i}"
                )
                percentages[side].append(float("nan"))
            else:
                percentage = (stance[i] / stride[i]) * 100
                percentages[side].append(percentage)
    return percentages
