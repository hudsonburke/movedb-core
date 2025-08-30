from fastapi import APIRouter, File, UploadFile

router = APIRouter(
    prefix="/upload",
    tags=["upload"]
)

@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    return {"filename": file.filename}
