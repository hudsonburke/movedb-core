from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .dependencies import create_db_and_tables
from .config import settings
from .routers.ingest import router as ingest_router
from .routers.upload import router as upload_router
from .routers.crud import router as crud_router_v1

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API for biomechanical motion capture data management and analysis",
    lifespan=lifespan,
)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include all routers
app.include_router(crud_router_v1)
app.include_router(ingest_router)
app.include_router(upload_router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to MoveDB API",
        "version": settings.VERSION,
        "docs_url": "/docs",
        "available_endpoints": {
            "crud": "/api/v1",
            "ingest": "/ingest", 
            "upload": "/upload",
            "opensim": "/opensim"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}
