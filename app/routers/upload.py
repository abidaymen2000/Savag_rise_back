# app/routers/upload.py

from typing import List
from fastapi import APIRouter, Depends, UploadFile, File
from ..schemas.image import ImageUploadOut, MultipleImageUploadOut
from app.utils.imagekit_upload import upload_to_imagekit
from app.dependencies_admin import require_permission

router = APIRouter(tags=["upload"])

@router.post("/upload-images", response_model=MultipleImageUploadOut)
async def upload_images(
    files: List[UploadFile] = File(...),
    _admin=Depends(require_permission("products")),
):
    urls = []
    for f in files:
        url = await upload_to_imagekit(f)
        urls.append(url)
    return MultipleImageUploadOut(urls=urls)
