"""Storage configuration for MoveDB."""

from pathlib import Path
from pydantic import BaseModel
from typing import Optional


class StorageConfig(BaseModel):  # TODO: Maybe switch to Pydantic BaseSettings
    """Storage configuration for HDF5 and database."""

    # Base directory for HDF5 files
    hdf5_base_dir: Path = Path("./data/hdf5_storage")

    # SQL database URL
    database_url: str = "sqlite:///./data/movedb.db"

    # HDF5 compression settings
    compression: str = "gzip"
    compression_opts: int = 4

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure directories exist
        self.hdf5_base_dir.mkdir(parents=True, exist_ok=True)


# Global configuration instance
_config: Optional[StorageConfig] = None


def get_storage_config() -> StorageConfig:
    """Get the global storage configuration."""
    global _config
    if _config is None:
        _config = StorageConfig()
    return _config


def set_storage_config(config: StorageConfig) -> None:
    """Set the global storage configuration."""
    global _config
    _config = config
