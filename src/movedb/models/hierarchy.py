from sqlalchemy import JSON
from .trial import Trial
from sqlmodel import Column, SQLModel, Field, Relationship
from typing import Any

class Session(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str

    subject_id: int | None = Field(default=None, foreign_key="subject.id")
    subject: "Subject" = Relationship(back_populates="sessions")
    trials: list[Trial] = Relationship(back_populates="session")

class Subject(SQLModel, table=True):
    id: int | None = Field(default = None, primary_key=True)
    name: str = Field(index=True, unique=True)
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    classification_id: int | None = Field(default=None, foreign_key="classification.id")
    classification: "Classification" = Relationship(back_populates="subjects")
    sessions: list[Session] = Relationship(back_populates="subject")

class Classification(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str
    description: str

    subjects: list[Subject] = Relationship(back_populates="classification")