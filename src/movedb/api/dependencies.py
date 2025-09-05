from typing import Annotated
from fastapi import Depends
from sqlmodel import SQLModel, create_engine, Session
from .config import settings
from ..models import *  # Ensure all models are imported for metadata

connect_args = {"check_same_thread": False}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
SessionDep = Annotated[Session, Depends(get_session)]
