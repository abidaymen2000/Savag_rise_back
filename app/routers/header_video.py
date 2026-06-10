from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.db import get_db
from app.dependencies_admin import get_current_admin
from app.schemas.header_video import (
    HeaderVideoConfig,
    HeaderVideoListOut,
    HeaderVideoUpdate,
    HeaderVideoUploadOut,
)
from app.utils.imagekit_video import (
    delete_header_video_from_imagekit,
    list_header_videos_from_imagekit,
    upload_header_video_to_imagekit,
)

router = APIRouter(tags=["header-video"])

SETTINGS_COLLECTION = "cms_settings"
HEADER_VIDEO_KEY = "store_header_video"


async def _get_header_video_doc(db):
    return await db[SETTINGS_COLLECTION].find_one({"_id": HEADER_VIDEO_KEY})


def _doc_to_config(doc) -> HeaderVideoConfig:
    return HeaderVideoConfig(**doc["value"])


@router.get("/storefront/header-video", response_model=HeaderVideoConfig)
async def read_storefront_header_video(db=Depends(get_db)):
    doc = await _get_header_video_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune video de header configuree")
    return _doc_to_config(doc)


@router.get("/admin/header-videos", response_model=HeaderVideoListOut)
async def admin_list_header_videos(
    _admin=Depends(get_current_admin),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    items = await list_header_videos_from_imagekit(limit=limit, skip=skip)
    return HeaderVideoListOut(items=items)


@router.get("/admin/header-video", response_model=HeaderVideoConfig)
async def admin_get_header_video(_admin=Depends(get_current_admin), db=Depends(get_db)):
    doc = await _get_header_video_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune video de header configuree")
    return _doc_to_config(doc)


@router.put("/admin/header-video", response_model=HeaderVideoConfig)
async def admin_update_header_video(
    payload: HeaderVideoUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    value = payload.model_dump()
    await db[SETTINGS_COLLECTION].update_one(
        {"_id": HEADER_VIDEO_KEY},
        {"$set": {"value": value}},
        upsert=True,
    )
    return HeaderVideoConfig(**value)


@router.post("/admin/header-video/upload", response_model=HeaderVideoUploadOut, status_code=201)
async def admin_upload_header_video(
    file: UploadFile = File(...),
    set_active: bool = Query(True, description="Definir cette video comme video active du header"),
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    asset = await upload_header_video_to_imagekit(file)
    config = HeaderVideoConfig(video=asset)

    if set_active:
        await db[SETTINGS_COLLECTION].update_one(
            {"_id": HEADER_VIDEO_KEY},
            {"$set": {"value": config.model_dump()}},
            upsert=True,
        )

    return HeaderVideoUploadOut(**config.model_dump())


@router.delete("/admin/header-videos/{file_id}", status_code=204)
async def admin_delete_header_video(
    file_id: str,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    await delete_header_video_from_imagekit(file_id)
    await db[SETTINGS_COLLECTION].delete_one(
        {"_id": HEADER_VIDEO_KEY, "value.video.file_id": file_id}
    )
