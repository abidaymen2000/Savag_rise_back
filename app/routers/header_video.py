from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.header_video import (
    HeaderVideoAsset,
    HeaderVideoConfig,
    HeaderVideoListOut,
    HeaderVideoUpdate,
    HeaderVideoUploadOut,
)
from app.utils.imagekit_video import (
    delete_header_video_from_imagekit,
    list_header_images_from_imagekit,
    list_header_videos_from_imagekit,
    upload_header_image_to_imagekit,
    upload_header_video_to_imagekit,
)

router = APIRouter(tags=["header-video"])

SETTINGS_COLLECTION = "cms_settings"
HEADER_VIDEO_KEY = "store_header_video"


async def _get_header_video_doc(db):
    return await db[SETTINGS_COLLECTION].find_one({"_id": HEADER_VIDEO_KEY})


def _doc_to_config(doc) -> HeaderVideoConfig:
    return HeaderVideoConfig(**doc["value"])


async def _save_header_config(db, config: HeaderVideoConfig) -> HeaderVideoConfig:
    value = config.model_dump()
    await db[SETTINGS_COLLECTION].update_one(
        {"_id": HEADER_VIDEO_KEY},
        {"$set": {"value": value}},
        upsert=True,
    )
    return HeaderVideoConfig(**value)


@router.get("/storefront/header-video", response_model=HeaderVideoConfig)
async def read_storefront_header_video(db=Depends(get_db)):
    doc = await _get_header_video_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune video de header configuree")
    return _doc_to_config(doc)


@router.get("/admin/header-videos", response_model=HeaderVideoListOut)
async def admin_list_header_videos(
    _admin=Depends(require_permission("header_video")),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    items = await list_header_videos_from_imagekit(limit=limit, skip=skip)
    return HeaderVideoListOut(items=items)


@router.get("/admin/header-video", response_model=HeaderVideoConfig)
async def admin_get_header_video(_admin=Depends(require_permission("header_video")), db=Depends(get_db)):
    doc = await _get_header_video_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune video de header configuree")
    return _doc_to_config(doc)


@router.put("/admin/header-video", response_model=HeaderVideoConfig)
async def admin_update_header_video(
    payload: HeaderVideoUpdate,
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    return await _save_header_config(db, HeaderVideoConfig(**payload.model_dump()))


@router.post("/admin/header-video/upload", response_model=HeaderVideoUploadOut, status_code=201)
async def admin_upload_header_video(
    file: UploadFile = File(...),
    set_active: bool = Query(True, description="Definir cette video comme video active du header"),
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    asset = await upload_header_video_to_imagekit(file)
    doc = await _get_header_video_doc(db)
    if doc:
        config = _doc_to_config(doc)
        config.video = asset
    else:
        config = HeaderVideoConfig(video=asset)

    if set_active:
        await _save_header_config(db, config)

    return HeaderVideoUploadOut(**config.model_dump())


@router.get("/admin/header-images", response_model=HeaderVideoListOut)
async def admin_list_header_images(
    _admin=Depends(require_permission("header_video")),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    items = await list_header_images_from_imagekit(limit=limit, skip=skip)
    return HeaderVideoListOut(items=items)


@router.post("/admin/header-image/upload", response_model=HeaderVideoUploadOut, status_code=201)
async def admin_upload_header_image(
    file: UploadFile = File(...),
    set_active: bool = Query(True, description="Definir cette image comme image active du hero"),
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    asset = await upload_header_image_to_imagekit(file)
    doc = await _get_header_video_doc(db)
    if doc:
        config = _doc_to_config(doc)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Configurez d'abord une video hero")

    if set_active:
        config.image = asset
        await _save_header_config(db, config)

    return HeaderVideoUploadOut(**config.model_dump())


@router.put("/admin/header-image", response_model=HeaderVideoConfig)
async def admin_select_header_image(
    image: HeaderVideoAsset,
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    doc = await _get_header_video_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune configuration hero")
    config = _doc_to_config(doc)
    config.image = image
    return await _save_header_config(db, config)


@router.delete("/admin/header-videos/{file_id}", status_code=204)
async def admin_delete_header_video(
    file_id: str,
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    await delete_header_video_from_imagekit(file_id)
    await db[SETTINGS_COLLECTION].delete_one(
        {"_id": HEADER_VIDEO_KEY, "value.video.file_id": file_id}
    )


@router.delete("/admin/header-images/{file_id}", status_code=204)
async def admin_delete_header_image(
    file_id: str,
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    await delete_header_video_from_imagekit(file_id)
    await db[SETTINGS_COLLECTION].update_one(
        {"_id": HEADER_VIDEO_KEY, "value.image.file_id": file_id},
        {"$unset": {"value.image": ""}},
    )
