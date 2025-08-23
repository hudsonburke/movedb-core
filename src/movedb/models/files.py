from pydantic import model_validator
import hashlib
import datetime
from sqlmodel import SQLModel, Field

class File(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    
    file_name: str = Field(index=True)
    file_path: str = Field(unique=True, description='Absolute path to the file')
    file_type: str
    file_size: int | None = None
    file_hash: str = Field(unique=True, description='SHA256 hash of the file')

    date_created: datetime.datetime
    last_modified: datetime.datetime
    
    @model_validator(mode='after')
    def _compute_file_hash(self):
        old_hash = self.file_hash
        hasher = hashlib.sha256()
        with open(self.file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        self.file_hash = hasher.hexdigest()
        if old_hash != self.file_hash:
            self.last_modified = datetime.datetime.now()
        return self
