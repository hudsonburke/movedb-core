from pathlib import Path
from pydantic import model_validator
from typing import Literal
import hashlib
import datetime
from sqlmodel import SQLModel, Field


class File(SQLModel):
    id: int | None = Field(default=None, primary_key=True)

    name: str = Field(index=True)
    path: str = Field(unique=True, description="Absolute path to the file")
    type: type
    size: int | None = None
    hash: str = Field(unique=True, description="SHA256 hash of the file", default="")

    date_created: datetime.datetime = Field(default_factory=datetime.datetime.now)
    last_modified: datetime.datetime

    @model_validator(mode="after")
    def _compute_hash(self):
        old_hash = self.hash
        hasher = hashlib.sha256()
        with open(self.path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        self.hash = hasher.hexdigest()
        if old_hash != self.hash:
            self.last_modified = datetime.datetime.now()
        return self

    def __enter__(self, mode: Literal["r", "rb", "w", "wb", "a"] = "rb"):
        try:
            path = Path(self.path)
            # Create parent directory if needed (for write/append modes)
            if mode in ("w", "wb", "a"):
                path.parent.mkdir(parents=True, exist_ok=True)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"File not found: {self.path}. "
                f"Ensure the file exists or use mode='w' to create it."
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to open file: {self.path}. "
                f"The file may be corrupted or opened by another process."
            ) from e
        return self.type(self.path, mode)

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.type.close()
        except Exception as e:
            raise RuntimeError(
                f"Failed to close file: {self.path}. Ensure the file is not corrupted."
            ) from e
