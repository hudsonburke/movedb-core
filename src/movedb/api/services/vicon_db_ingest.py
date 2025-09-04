from typing import Any
from sqlmodel import Session, select
from ...models import Subject, CaptureSession, Trial
from ...ingest.vicon_scan import discover_vicon_directory

def _ensure_subject(session: Session, subject_name: str) -> Subject:
    subject = session.exec(select(Subject).where(Subject.name == subject_name)).first()
    if subject is None:
        subject = Subject(name=subject_name)
        session.add(subject)
        session.commit()
        session.refresh(subject)
    return subject


def _ensure_capture_session(session: Session, session_name: str) -> CaptureSession:
    cs = session.exec(select(CaptureSession).where(CaptureSession.name == session_name)).first()
    if cs is None:
        cs = CaptureSession(name=session_name)
        session.add(cs)
        session.commit()
        session.refresh(cs)
    return cs


def _ensure_trial(session: Session, trial_name: str, capture_session: CaptureSession) -> Trial:
    trial = session.exec(
        select(Trial).where(Trial.name == trial_name, Trial.capture_session_id == capture_session.id)
    ).first()
    if trial is None:
        trial = Trial(name=trial_name, capture_session_id=capture_session.id)
        session.add(trial)
        session.commit()
        session.refresh(trial)
    return trial


def scan_vicon_directory(session: Session, root: str) -> dict[str, Any]:
    discovery = discover_vicon_directory(root)

    subjects_created = 0
    sessions_created = 0
    trials_created = 0

    for subject_info in discovery["subjects"]:
        subject = session.exec(select(Subject).where(Subject.name == subject_info["name"])).first()
        if subject is None:
            subject = _ensure_subject(session, subject_info["name"])
            subjects_created += 1

        for cs_info in subject_info["capture_sessions"]:
            cs = session.exec(select(CaptureSession).where(CaptureSession.name == cs_info["name"])) .first()
            if cs is None:
                cs = _ensure_capture_session(session, cs_info["name"])
                sessions_created += 1

            for trial_info in cs_info["trials"]:
                trial = session.exec(
                    select(Trial).where(Trial.name == trial_info["name"], Trial.capture_session_id == cs.id)
                ).first()
                if trial is None:
                    trial = _ensure_trial(session, trial_info["name"], cs)
                    trial.subjects.append(subject)
                    session.add(trial)
                    session.commit()
                    session.refresh(trial)
                    trials_created += 1

    return {
        "root": root,
        "subjects_created": subjects_created,
        "sessions_created": sessions_created,
        "trials_created": trials_created,
    }


