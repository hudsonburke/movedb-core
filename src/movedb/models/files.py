import hashlib
import datetime
from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel

class File(BaseModel):
    id: int
    
    file_name: str
    file_path: str
    file_type: str
    file_size: int
    file_hash: str = Field(unique=True, description='SHA256 hash of the file')

    date_created: datetime.datetime
    last_modified: datetime.datetime


