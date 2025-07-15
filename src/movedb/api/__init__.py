"""FastAPI application for MoveDB Core."""

try:
    from .app import app
    from .database import engine, create_db_and_tables
    from .models import *
    from .enhanced_models import *
    from .services import *
    
    __all__ = [
        "app",
        "engine", 
        "create_db_and_tables",
    ]
except ImportError as e:
    # Handle missing dependencies gracefully
    import warnings
    warnings.warn(
        f"FastAPI integration dependencies not available: {e}. "
        "Install with: pip install fastapi uvicorn sqlmodel psycopg2-binary",
        UserWarning
    )
