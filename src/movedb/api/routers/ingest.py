from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any
from ..dependencies import get_session
from ..services.vicon_db_ingest import scan_vicon_directory

router = APIRouter(prefix="/ingest", tags=["ingest"])
@router.post("/scan")
def scan_vicon_database(
    root: str = Query(..., description="Root directory of the Vicon Nexus database"),
    session=Depends(get_session),
) -> dict[str, Any]:
    try:
        return scan_vicon_directory(session=session, root=root)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))


