from sqlmodel import SQLModel, Field, Relationship
from .trial import Trial

class TrialSubjectLink(SQLModel, table=True):
    trial_id: int | None = Field(default = None, foreign_key="trial.id", primary_key=True)
    subject_id: int | None = Field(default = None, foreign_key="subject.id", primary_key=True)

class Subject(SQLModel, table=True):
    id: int | None = Field(default = None, primary_key=True)
    name: str = Field(index=True, unique=True)
    trials: list[Trial] = Relationship(back_populates="subjects", link_model=TrialSubjectLink)
