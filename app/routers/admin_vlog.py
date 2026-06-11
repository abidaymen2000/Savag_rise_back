from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.db import get_db
from app.dependencies_admin import get_current_admin
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
from app.config import settings
from app.utils.imagekit_client import ik
from app.utils.imagekit_media import upload_vlog_media_to_imagekit
from app.utils.imagekit_media import VLOG_MEDIA_FOLDERS
from app.utils.vlog_service import (
    CHAPTERS_COLLECTION,
    EPISODES_COLLECTION,
    MEDIA_COLLECTION,
    SETTINGS_COLLECTION,
    VLOG_SETTINGS_KEY,
    chapter_out,
    chapter_with_episodes,
    episode_out,
    now_utc,
    settings_out,
    unique_chapter_slug,
    validate_object_id,
)

router = APIRouter(prefix="/admin/vlog", tags=["admin-vlog"])


@router.get("/settings", response_model=VlogSettingsOut)
async def admin_get_vlog_settings(_admin=Depends(get_current_admin), db=Depends(get_db)):
    return await settings_out(db)


@router.put("/settings", response_model=VlogSettingsOut)
async def admin_update_vlog_settings(
    payload: VlogSettingsUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    value = payload.model_dump()
    updated_at = now_utc()
    await db[SETTINGS_COLLECTION].update_one(
        {"_id": VLOG_SETTINGS_KEY},
        {"$set": {"value": value, "updated_at": updated_at}},
        upsert=True,
    )
    return VlogSettingsOut(**value, updated_at=updated_at)


@router.post("/media/upload", response_model=VlogMediaAsset, status_code=201)
async def admin_upload_vlog_media(
    media_type: MediaType = Query(...),
    file: UploadFile = File(...),
    _admin=Depends(get_current_admin),
):
    asset = await upload_vlog_media_to_imagekit(file, media_type)
    return VlogMediaAsset(**asset)


@router.get("/media/upload-auth", response_model=ImageKitDirectUploadAuth)
async def admin_get_vlog_media_upload_auth(
    media_type: MediaType = Query(...),
    _admin=Depends(get_current_admin),
):
    auth = ik.get_authentication_parameters()
    return ImageKitDirectUploadAuth(
        token=auth["token"],
        expire=auth["expire"],
        signature=auth["signature"],
        public_key=settings.imagekit_public_key.get_secret_value(),
        url_endpoint=str(settings.imagekit_url_endpoint),
        folder=VLOG_MEDIA_FOLDERS[media_type],
    )


def _media_out(doc) -> VlogMediaOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return VlogMediaOut(**payload)


@router.post("/media/register", response_model=VlogMediaOut, status_code=201)
async def admin_register_uploaded_vlog_media(
    payload: VlogMediaRegister,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    data = payload.model_dump(by_alias=False)
    data["created_at"] = now_utc()
    res = await db[MEDIA_COLLECTION].insert_one(data)
    created = await db[MEDIA_COLLECTION].find_one({"_id": res.inserted_id})
    return _media_out(created)


@router.get("/media", response_model=List[VlogMediaOut])
async def admin_list_vlog_media(
    media_type: Optional[MediaType] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    filters = {}
    if media_type:
        filters["media_type"] = media_type
    docs = await db[MEDIA_COLLECTION].find(filters).sort("_id", -1).skip(skip).limit(limit).to_list(length=limit)
    return [_media_out(doc) for doc in docs]


@router.get("/chapters", response_model=List[VlogChapterWithEpisodesOut])
async def admin_list_vlog_chapters(_admin=Depends(get_current_admin), db=Depends(get_db)):
    chapter_docs = await db[CHAPTERS_COLLECTION].find().sort("order", 1).to_list(length=100)
    return [await chapter_with_episodes(db, chapter, public_only=False) for chapter in chapter_docs]


@router.post("/chapters", response_model=VlogChapterOut, status_code=201)
async def admin_create_vlog_chapter(
    payload: VlogChapterCreate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    now = now_utc()
    data = payload.model_dump()
    data["slug"] = await unique_chapter_slug(db, data["title"], data.get("slug"))
    data["created_at"] = now
    data["updated_at"] = now
    res = await db[CHAPTERS_COLLECTION].insert_one(data)
    created = await db[CHAPTERS_COLLECTION].find_one({"_id": res.inserted_id})
    return chapter_out(created)


@router.get("/chapters/{chapter_id}", response_model=VlogChapterWithEpisodesOut)
async def admin_get_vlog_chapter(chapter_id: str, _admin=Depends(get_current_admin), db=Depends(get_db)):
    oid = validate_object_id(chapter_id, "Chapitre ID")
    chapter = await db[CHAPTERS_COLLECTION].find_one({"_id": oid})
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    return await chapter_with_episodes(db, chapter, public_only=False)


@router.put("/chapters/{chapter_id}", response_model=VlogChapterOut)
async def admin_update_vlog_chapter(
    chapter_id: str,
    payload: VlogChapterUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(chapter_id, "Chapitre ID")
    existing = await db[CHAPTERS_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")

    data = payload.model_dump(exclude_unset=True)
    if "title" in data or "slug" in data:
        data["slug"] = await unique_chapter_slug(db, data.get("title", existing["title"]), data.get("slug"), exclude_id=oid)
    data["updated_at"] = now_utc()
    await db[CHAPTERS_COLLECTION].update_one({"_id": oid}, {"$set": data})
    updated = await db[CHAPTERS_COLLECTION].find_one({"_id": oid})
    return chapter_out(updated)


@router.delete("/chapters/{chapter_id}", status_code=204)
async def admin_delete_vlog_chapter(
    chapter_id: str,
    delete_episodes: bool = Query(False),
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(chapter_id, "Chapitre ID")
    existing = await db[CHAPTERS_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    await db[CHAPTERS_COLLECTION].delete_one({"_id": oid})
    if delete_episodes:
        await db[EPISODES_COLLECTION].delete_many({"chapter_id": oid})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/chapters/{chapter_id}/short-film", response_model=VlogChapterOut)
async def admin_update_chapter_short_film(
    chapter_id: str,
    payload: ShortFilmUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(chapter_id, "Chapitre ID")
    existing = await db[CHAPTERS_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    await db[CHAPTERS_COLLECTION].update_one(
        {"_id": oid},
        {"$set": {"short_film": payload.model_dump(), "updated_at": now_utc()}},
    )
    updated = await db[CHAPTERS_COLLECTION].find_one({"_id": oid})
    return chapter_out(updated)


@router.post("/chapters/{chapter_id}/episodes", response_model=VlogEpisodeOut, status_code=201)
async def admin_create_vlog_episode(
    chapter_id: str,
    payload: VlogEpisodeCreate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    chapter_oid = validate_object_id(chapter_id, "Chapitre ID")
    if not await db[CHAPTERS_COLLECTION].find_one({"_id": chapter_oid}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")

    now = now_utc()
    data = payload.model_dump()
    data["chapter_id"] = chapter_oid
    data["created_at"] = now
    data["updated_at"] = now
    res = await db[EPISODES_COLLECTION].insert_one(data)
    created = await db[EPISODES_COLLECTION].find_one({"_id": res.inserted_id})
    return await episode_out(db, created)


@router.get("/chapters/{chapter_id}/episodes", response_model=List[VlogEpisodeOut])
async def admin_list_vlog_episodes(chapter_id: str, _admin=Depends(get_current_admin), db=Depends(get_db)):
    chapter_oid = validate_object_id(chapter_id, "Chapitre ID")
    docs = await db[EPISODES_COLLECTION].find({"chapter_id": chapter_oid}).sort("order", 1).to_list(length=50)
    return [await episode_out(db, doc) for doc in docs]


@router.put("/episodes/{episode_id}", response_model=VlogEpisodeOut)
async def admin_update_vlog_episode(
    episode_id: str,
    payload: VlogEpisodeUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(episode_id, "Episode ID")
    existing = await db[EPISODES_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode non trouve")
    data = payload.model_dump(exclude_unset=True)
    data["updated_at"] = now_utc()
    await db[EPISODES_COLLECTION].update_one({"_id": oid}, {"$set": data})
    updated = await db[EPISODES_COLLECTION].find_one({"_id": oid})
    return await episode_out(db, updated)


@router.delete("/episodes/{episode_id}", status_code=204)
async def admin_delete_vlog_episode(episode_id: str, _admin=Depends(get_current_admin), db=Depends(get_db)):
    oid = validate_object_id(episode_id, "Episode ID")
    existing = await db[EPISODES_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode non trouve")
    await db[EPISODES_COLLECTION].delete_one({"_id": oid})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
