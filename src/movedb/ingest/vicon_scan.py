import os
from typing import Any, TypedDict
from ..models import Subject, CaptureSession, Trial

class TrialInfo(TypedDict):
    name: str

class CaptureSessionInfo(TypedDict):
    name: str
    trials: list[TrialInfo]

class SubjectInfo(TypedDict):
    name: str
    capture_sessions: list[CaptureSessionInfo]

class DiscoveryResult(TypedDict):
    root: str
    subjects: list[SubjectInfo]

def parse_enf_file(file_path: str, encoding: str = "utf-8") -> dict[str, str]:
    """
    Parse an .enf file and return key-value pairs.

    Args:
        file_path: Path to the .enf file
        encoding: File encoding (default: utf-8)

    Returns:
        Dictionary with lowercase keys and their values
    """
    data = {}
    try:
        with open(file_path, "r", encoding=encoding) as file:
            for line in file:
                line = line.lstrip("\ufeff").strip()
                if "=" in line:
                    parts = line.split("=", 1)
                    key = parts[0].strip() if len(parts) > 0 else ""
                    value = parts[1].strip() if len(parts) > 1 else ""
                    if key:
                        data[key.lower()] = value
    except UnicodeDecodeError:
        # Try with a different encoding if UTF-8 fails
        with open(file_path, "r", encoding="latin-1") as file:
            for line in file:
                line = line.lstrip("\ufeff").strip()
                if "=" in line:
                    parts = line.split("=", 1)
                    key = parts[0].strip() if len(parts) > 0 else ""
                    value = parts[1].strip() if len(parts) > 1 else ""
                    if key:
                        data[key.lower()] = value
    return data

def discover_vicon_directory(root: str) -> DiscoveryResult:
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Root directory not found: {root}")

    subjects: list[SubjectInfo] = []

    # Structure: {root}/{Classifications}/{Subjects}/{CaptureSessions}/{Trials(.enf/.c3d)}
    for classification_name in sorted(os.listdir(root)):
        classification_path = os.path.join(root, classification_name)
        if not os.path.isdir(classification_path):
            continue

        for subject_name in sorted(os.listdir(classification_path)):
            subject_path = os.path.join(classification_path, subject_name)
            if not os.path.isdir(subject_path):
                continue

            sessions: list[CaptureSessionInfo] = []
            for capture_session_name in sorted(os.listdir(subject_path)):
                capture_session_path = os.path.join(subject_path, capture_session_name)
                if not os.path.isdir(capture_session_path):
                    continue

                trial_basenames: set[str] = set()
                for file_name in os.listdir(capture_session_path):
                    if file_name.lower().endswith((".c3d", ".enf")):
                        base, _ = os.path.splitext(file_name)
                        trial_basenames.add(base)

                sessions.append(
                    {
                        "name": capture_session_name,
                        "trials": [{"name": t} for t in sorted(trial_basenames)],
                    }
                )

            subjects.append({"name": subject_name, "capture_sessions": sessions})

    return {"root": root, "subjects": subjects}


def build_in_memory_hierarchy(root: str) -> dict[str, Any]:
    """
    Build an in-memory representation of the hierarchy using SQLModel objects
    without requiring a database connection. Objects are not persisted.

    Returns a dict with lists of constructed model instances you can use in
    analysis or pass to persistence later.
    """
    discovery = discover_vicon_directory(root)

    subjects: list[Subject] = []
    capture_sessions: list[CaptureSession] = []
    trials: list[Trial] = []

    for subject_info in discovery["subjects"]:
        subject = Subject(name=subject_info["name"])  # id remains None
        subjects.append(subject)

        for cs_info in subject_info["capture_sessions"]:
            cs = CaptureSession(name=cs_info["name"])  # id remains None
            capture_sessions.append(cs)

            for trial_info in cs_info["trials"]:
                trial = Trial(name=trial_info["name"], capture_session=cs)
                # Link trial to subject (association in-memory)
                trial.subjects.append(subject)
                trials.append(trial)

    return {
        "root": discovery["root"],
        "subjects": subjects,
        "capture_sessions": capture_sessions,
        "trials": trials,
    }


