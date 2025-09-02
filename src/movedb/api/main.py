from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .dependencies import create_db_and_tables, get_session
from .config import settings
from fastcrud import crud_router
from ..models import Trial
from .routers.ingest import router as ingest_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
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

trial_router = crud_router(
    session=Depends(get_session),
    model=Trial,
    create_schema=Trial,
    update_schema=Trial,
    path="/trials",
    tags=["trials"],
)
app.include_router(trial_router)
app.include_router(ingest_router)

@app.get("/")
async def root():
    return {"message": "Hello there"}
