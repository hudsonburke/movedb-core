from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from .trial import Trial
    from .hierarchy import CaptureSession, Subject

class CaptureSessionGroupLink(SQLModel, table=True):
    capture_session_id: int | None = Field(
        default=None, foreign_key="capture_session.id", primary_key=True
    )
    group_id: int | None = Field(
        default=None, foreign_key="group.id", primary_key=True
    )

class CaptureSessionGroup(SQLModel, table=True):
    id: int | None = Field(default = None, primary_key=True)
    name: str = Field(index=True)

    capture_sessions: list["CaptureSession"] = Relationship(back_populates="groups", link_model=CaptureSessionGroupLink)
    
class SubjectGroupLink(SQLModel, table=True):
    subject_id: int | None = Field(
        default=None, foreign_key="subject.id", primary_key=True
    )
    group_id: int | None = Field(
        default=None, foreign_key="group.id", primary_key=True
    )

class SubjectGroup(SQLModel, table=True):
    id: int | None = Field(default = None, primary_key=True)
    name: str = Field(index=True)

    subjects: list["Subject"] = Relationship(back_populates="groups", link_model=SubjectGroupLink)

class TrialGroupLink(SQLModel, table=True):
    trial_id: int | None= Field(
        default=None, foreign_key="trial.id", primary_key=True
    )
    group_id: int | None = Field(
        default=None, foreign_key="group.id", primary_key=True
    )

class TrialGroup(SQLModel, table=True):
    id: int | None = Field(default = None, primary_key=True)
    name: str = Field(index=True)

    trials: list["Trial"] = Relationship(back_populates="groups")
