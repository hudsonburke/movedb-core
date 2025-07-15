"""Database configuration for the FastAPI application."""

import os
from sqlmodel import SQLModel, create_engine
from typing import Optional

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/movedb")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True,
    pool_recycle=300,
)


def create_db_and_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def get_database_url() -> str:
    """Get the database URL."""
    return DATABASE_URL
