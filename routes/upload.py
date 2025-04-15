from fastapi import APIRouter, File, UploadFile
import shutil
import os

router = APIRouter()

UPLOAD_FOLDER = "static/uploads/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """接收图片并保存"""
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename, "file_path": file_path}