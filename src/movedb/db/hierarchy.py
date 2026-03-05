from sqlalchemy import JSON
from sqlmodel import Column, SQLModel, Field, Relationship, UniqueConstraint
from typing import Any, TYPE_CHECKING
from datetime import datetime
from .groups import CaptureSessionGroupLink, SubjectGroupLink

if TYPE_CHECKING:
    from .trial import Trial
    from .groups import CaptureSessionGroup, SubjectGroup


class CaptureSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime | None = None

    subject_parameters: list["SubjectSessionParameters"] = Relationship(
        back_populates="capture_session"
    )
    trials: list["Trial"] = Relationship(back_populates="capture_session")
    groups: list["CaptureSessionGroup"] = Relationship(
        back_populates="capture_sessions", link_model=CaptureSessionGroupLink
    )


class SubjectSessionParameters(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "subject_id", "capture_session_id", name="unique_subject_session"
        ),
    )
    id: int | None = Field(default=None, primary_key=True)

    subject_id: int | None = Field(default=None, foreign_key="subject.id")
    subject: "Subject" = Relationship(back_populates="session_parameters")

    capture_session_id: int | None = Field(
        default=None, foreign_key="capturesession.id"
    )
    capture_session: "CaptureSession" = Relationship(
        back_populates="subject_parameters"
    )

    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class TrialSubjectLink(SQLModel, table=True):
    trial_id: int | None = Field(
        default=None, foreign_key="trial.id", primary_key=True
    )
    subject_id: int | None = Field(
        default=None, foreign_key="subject.id", primary_key=True
    )


class Subject(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    session_parameters: list["SubjectSessionParameters"] = Relationship(
        back_populates="subject"
    )
    trials: list["Trial"] = Relationship(
        back_populates="subjects", link_model=TrialSubjectLink
    )
    groups: list["SubjectGroup"] = Relationship(
        back_populates="subjects", link_model=SubjectGroupLink
    )
