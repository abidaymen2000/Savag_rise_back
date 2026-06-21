from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.header_video import (
    HeaderVideoAsset,
    HeaderVideoConfig,
    HeaderVideoListOut,
    HeaderVideoUpdate,
    HeaderVideoUploadOut,
)
from app.services.services_cms.header_video_service import (
    delete_header_image,
    delete_header_video,
    get_header_video_config,
    list_header_images,
    list_header_videos,
    select_header_image,
    update_header_video,
    upload_header_image,
    upload_header_video,
)

router = APIRouter(tags=["header-video"])

@router.get("/admin/header-videos", response_model=HeaderVideoListOut)
async def admin_list_header_videos(
    _admin=Depends(require_permission("header_video")),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    return await list_header_videos(limit=limit, skip=skip)


@router.get("/admin/header-video", response_model=HeaderVideoConfig)
async def admin_get_header_video(_admin=Depends(require_permission("header_video")), db=Depends(get_db)):
    return await get_header_video_config(db)


@router.put("/admin/header-video", response_model=HeaderVideoConfig)
async def admin_update_header_video(
    payload: HeaderVideoUpdate,
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    return await update_header_video(db, payload)


@router.post("/admin/header-video/upload", response_model=HeaderVideoUploadOut, status_code=201)
async def admin_upload_header_video(
    file: UploadFile = File(...),
    set_active: bool = Query(True, description="Definir cette video comme video active du header"),
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    return await upload_header_video(db, file, set_active)


@router.get("/admin/header-images", response_model=HeaderVideoListOut)
async def admin_list_header_images(
    _admin=Depends(require_permission("header_video")),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    return await list_header_images(limit=limit, skip=skip)


@router.post("/admin/header-image/upload", response_model=HeaderVideoUploadOut, status_code=201)
async def admin_upload_header_image(
    file: UploadFile = File(...),
    set_active: bool = Query(True, description="Definir cette image comme image active du hero"),
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    return await upload_header_image(db, file, set_active)


@router.put("/admin/header-image", response_model=HeaderVideoConfig)
async def admin_select_header_image(
    image: HeaderVideoAsset,
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    return await select_header_image(db, image)


@router.delete("/admin/header-videos/{file_id}", status_code=204)
async def admin_delete_header_video(
    file_id: str,
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    await delete_header_video(db, file_id)


@router.delete("/admin/header-images/{file_id}", status_code=204)
async def admin_delete_header_image(
    file_id: str,
    _admin=Depends(require_permission("header_video")),
    db=Depends(get_db),
):
    await delete_header_image(db, file_id)
