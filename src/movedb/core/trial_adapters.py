import ezc3d
import pickle
import numpy as np
import scipy.io as sio
from .models import Trial, Event, Points, Analogs, Subject

def trial_from_c3d(
    c3d_object: ezc3d.c3d,
    trial_name: str = "",
    session_name: str = "",
    classification: str = "",
) -> Trial:

    subject_names = get_c3d_param(
        c3d_object,
        "SUBJECTS",
        "NAMES",
        default=Trial.model_fields["subject_names"].default,
    )
    parameters = {}
    if "PROCESSING" in c3d_object.parameters:
        for key, value in c3d_object.parameters["PROCESSING"].items():
            arr = value.get("value", [])
            if isinstance(arr, list) or isinstance(arr, np.ndarray):
                parameters[key] = arr[0] if len(arr) == 1 else arr
            else:
                parameters[key] = arr

    num_events = get_c3d_param(c3d_object, "EVENT", "USED", default=[0])[0]

    trial = Trial(
        name=trial_name,
        session_name=session_name,
        classification=classification,
        subject_names=subject_names,
        points=Points.from_c3d(c3d_object),
        analogs=Analogs.from_c3d(c3d_object),
        force_platforms=[
            EZForcePlatform.from_c3d(c3d_object, index=i)
            for i in range(len(c3d_object.data["platform"]))
        ],
        parameters=parameters,
        events=[
            Event.from_c3d(c3d_object, index=i)
            for i in range(int(num_events))
        ],
    )
    return trial

def trial_from_c3d_file(
    file_path: str,
    trial_name: str = "",
    session_name: str = "",
    classification: str = "",
) -> Trial:
    """
    Create a Trial instance from a C3D file.
    """
    c3d = ezc3d.c3d(file_path, extract_forceplat_data=True)
    trial = trial_from_c3d(
        c3d,
        trial_name=trial_name,
        session_name=session_name,
        classification=classification,
    )
    return trial

def trial_to_pkl(trial: Trial, path: str):
    """
    Save the Trial to a pickle file.
    Args:
        path (str): Path to save the pickle file.
    """
    with open(path, "wb") as f:
        pickle.dump(trial, f)

def trial_from_pkl(path: str) -> Trial:
    """
    Load a Trial from a pickle file.
    Args:
        trial:
        path (str): Path to the pickle file.
    Returns:
        Trial: The loaded Trial object.
    """
    with open(path, "rb") as f:
        data = pickle.load(f)
    if not isinstance(data, Trial):
        raise ValueError(f"Loaded data is not an instance of Trial: got {type(data)}")
    return data

def trial_from_vicon_nexus(connection: "ViconNexus") -> Trial:
    """
    Create a Trial instance from an open trial in Vicon Nexus.
    This method requires the Vicon Nexus API to be installed and configured.
    https://pycgm2.readthedocs.io/en/latest/Pages/thirdParty/NexusAPI.html
    """
    raise NotImplementedError("Vicon Nexus API integration is not implemented yet.")

# WARNING: I hate this function, so it's probably not well maintained
def trial_to_mat(trial: Trial, filepath: str):
    """
    Export trial data to a .mat file.
    The structure of the .mat file will include:
    - Info: Metadata about the trial, including name, session, subjects, classification, camera rate, and subject parameters.
    - Events: A structure containing the total number of frames, region of interest, and lists of event frames for foot strikes, foot offs, and general events.
    - Markers: A dictionary of marker data, excluding residuals.
    - Analog: A dictionary of analog data, with keys modified to replace '.' with '_', and time as a separate list.
    Args:
        filepath (str): Path to save the .mat file.
    """
    import scipy.io as sio

    mat_dict = {}
    mat_dict["Info"] = {
        "TrialName": trial.name,
        "Session": trial.session_name,
        "Subjects": trial.subject_names,
        "Classification": trial.classification,
        "CameraRate": trial.points.rate,
        "SubjectParameters": trial.parameters,
    }

    mat_dict["Events"] = {
        "TotalFrames": trial.points.last_frame + 1 - trial.points.first_frame,
        "RegionOfInterest": [
            trial.points.first_frame,
            trial.points.last_frame,
        ],
        "LeftFootStrike": [
            event.get_frame(trial.points.rate)
            for event in trial.get_events(label="Foot Strike", context="Left")
        ],
        "RightFootStrike": [
            event.get_frame(trial.points.rate)
            for event in trial.get_events(label="Foot Strike", context="Right")
        ],
        "LeftFootOff": [
            event.get_frame(trial.points.rate)
            for event in trial.get_events(label="Foot Off", context="Left")
        ],
        "RightFootOff": [
            event.get_frame(trial.points.rate)
            for event in trial.get_events(label="Foot Off", context="Right")
        ],
        "General": [
            event.get_frame(trial.points.rate)
            for event in trial.get_events(context="General")
        ],
    }

    mat_dict["Markers"] = trial.points.to_dict(include_residual=False)

    # Convert analog keys to replace '.' with '_'
    analog_dict = trial.analogs.to_df().to_dict()
    analog_dict = {k.replace(".", "_"): v for k, v in analog_dict.items()}
    mat_dict["Analog"] = analog_dict
    mat_dict["Analog"]["Time"] = trial.analogs.time.tolist()

    sio.savemat(filepath, mat_dict)

