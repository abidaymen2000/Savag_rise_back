from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.vlog import (
    ImageKitDirectUploadAuth,
    MediaType,
    ShortFilmUpdate,
    VlogChapterCreate,
    VlogChapterOut,
    VlogChapterUpdate,
    VlogChapterWithEpisodesOut,
    VlogEpisodeCreate,
    VlogEpisodeOut,
    VlogEpisodeUpdate,
    VlogMediaAsset,
    VlogMediaOut,
    VlogMediaRegister,
    VlogSettingsOut,
    VlogSettingsUpdate,
)
from app.services.services_cms import admin_vlog_service
from app.services.services_cms.vlog_service import settings_out


router = APIRouter(prefix="/admin/vlog", tags=["admin-vlog"])


@router.get("/settings", response_model=VlogSettingsOut)
async def admin_get_vlog_settings(_admin=Depends(require_permission("vlog")), db=Depends(get_db)):
    return await settings_out(db)


@router.put("/settings", response_model=VlogSettingsOut)
async def admin_update_vlog_settings(
    payload: VlogSettingsUpdate,
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    return await admin_vlog_service.update_settings(db, payload)


@router.post("/media/upload", response_model=VlogMediaAsset, status_code=201)
async def admin_upload_vlog_media(
    media_type: MediaType = Query(...),
    file: UploadFile = File(...),
    _admin=Depends(require_permission("vlog")),
):
    return await admin_vlog_service.upload_media(file, media_type)


@router.get("/media/upload-auth", response_model=ImageKitDirectUploadAuth)
async def admin_get_vlog_media_upload_auth(
    media_type: MediaType = Query(...),
    _admin=Depends(require_permission("vlog")),
):
    return await admin_vlog_service.get_upload_auth(media_type)


@router.post("/media/register", response_model=VlogMediaOut, status_code=201)
async def admin_register_uploaded_vlog_media(
    payload: VlogMediaRegister,
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    return await admin_vlog_service.register_media(db, payload)


@router.get("/media", response_model=List[VlogMediaOut])
async def admin_list_vlog_media(
    media_type: Optional[MediaType] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    return await admin_vlog_service.list_media(db, media_type, limit, skip)


@router.get("/chapters", response_model=List[VlogChapterWithEpisodesOut])
async def admin_list_vlog_chapters(_admin=Depends(require_permission("vlog")), db=Depends(get_db)):
    return await admin_vlog_service.list_chapters(db)


@router.post("/chapters", response_model=VlogChapterOut, status_code=201)
async def admin_create_vlog_chapter(
    payload: VlogChapterCreate,
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    return await admin_vlog_service.create_chapter(db, payload)


@router.get("/chapters/{chapter_id}", response_model=VlogChapterWithEpisodesOut)
async def admin_get_vlog_chapter(chapter_id: str, _admin=Depends(require_permission("vlog")), db=Depends(get_db)):
    return await admin_vlog_service.get_chapter(db, chapter_id)


@router.put("/chapters/{chapter_id}", response_model=VlogChapterOut)
async def admin_update_vlog_chapter(
    chapter_id: str,
    payload: VlogChapterUpdate,
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    return await admin_vlog_service.update_chapter(db, chapter_id, payload)


@router.delete("/chapters/{chapter_id}", status_code=204)
async def admin_delete_vlog_chapter(
    chapter_id: str,
    delete_episodes: bool = Query(False),
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    await admin_vlog_service.delete_chapter(db, chapter_id, delete_episodes)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/chapters/{chapter_id}/short-film", response_model=VlogChapterOut)
async def admin_update_chapter_short_film(
    chapter_id: str,
    payload: ShortFilmUpdate,
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    return await admin_vlog_service.update_chapter_short_film(db, chapter_id, payload)


@router.post("/chapters/{chapter_id}/episodes", response_model=VlogEpisodeOut, status_code=201)
async def admin_create_vlog_episode(
    chapter_id: str,
    payload: VlogEpisodeCreate,
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    return await admin_vlog_service.create_episode(db, chapter_id, payload)


@router.get("/chapters/{chapter_id}/episodes", response_model=List[VlogEpisodeOut])
async def admin_list_vlog_episodes(chapter_id: str, _admin=Depends(require_permission("vlog")), db=Depends(get_db)):
    return await admin_vlog_service.list_episodes(db, chapter_id)


@router.put("/episodes/{episode_id}", response_model=VlogEpisodeOut)
async def admin_update_vlog_episode(
    episode_id: str,
    payload: VlogEpisodeUpdate,
    _admin=Depends(require_permission("vlog")),
    db=Depends(get_db),
):
    return await admin_vlog_service.update_episode(db, episode_id, payload)


@router.delete("/episodes/{episode_id}", status_code=204)
async def admin_delete_vlog_episode(episode_id: str, _admin=Depends(require_permission("vlog")), db=Depends(get_db)):
    await admin_vlog_service.delete_episode(db, episode_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
