from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies_admin import require_permission
from app.schemas.image import MultipleImageUploadOut
from app.services.services_cms.imagekit_upload import upload_to_imagekit


router = APIRouter(tags=["admin-upload"])


@router.post("/upload-images", response_model=MultipleImageUploadOut)
async def upload_images(
    files: List[UploadFile] = File(...),
    _admin=Depends(require_permission("products")),
):
    urls = []
    for file in files:
        urls.append(await upload_to_imagekit(file))
    return MultipleImageUploadOut(urls=urls)
