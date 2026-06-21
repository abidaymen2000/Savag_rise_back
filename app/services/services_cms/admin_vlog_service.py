from typing import List, Optional

from fastapi import HTTPException, UploadFile, status

from app.config import settings
from app.crud import vlog as vlog_crud
from app.schemas.vlog import (
    ImageKitDirectUploadAuth,
    MediaType,
    VlogChapterOut,
    VlogChapterWithEpisodesOut,
    VlogEpisodeOut,
    VlogMediaAsset,
    VlogMediaOut,
    VlogSettingsOut,
)
from app.services.services_cms.imagekit_client import ik
from app.services.services_cms.imagekit_media import VLOG_MEDIA_FOLDERS, upload_vlog_media_to_imagekit
from app.services.services_cms.vlog_service import (
    chapter_out,
    chapter_with_episodes,
    episode_out,
    now_utc,
    settings_out,
    unique_chapter_slug,
    validate_object_id,
)


async def update_settings(db, payload) -> VlogSettingsOut:
    value = payload.model_dump()
    updated_at = now_utc()
    await vlog_crud.save_vlog_settings(db, value, updated_at)
    return VlogSettingsOut(**value, updated_at=updated_at)


async def upload_media(file: UploadFile, media_type: MediaType) -> VlogMediaAsset:
    asset = await upload_vlog_media_to_imagekit(file, media_type)
    return VlogMediaAsset(**asset)


async def get_upload_auth(media_type: MediaType) -> ImageKitDirectUploadAuth:
    auth = ik.get_authentication_parameters()
    return ImageKitDirectUploadAuth(
        token=auth["token"],
        expire=auth["expire"],
        signature=auth["signature"],
        public_key=settings.imagekit_public_key.get_secret_value(),
        url_endpoint=str(settings.imagekit_url_endpoint),
        folder=VLOG_MEDIA_FOLDERS[media_type],
    )


def media_out(doc) -> VlogMediaOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return VlogMediaOut(**payload)


async def register_media(db, payload) -> VlogMediaOut:
    data = payload.model_dump(by_alias=False)
    data["created_at"] = now_utc()
    res = await vlog_crud.insert_media(db, data)
    created = await vlog_crud.find_media_by_id(db, res.inserted_id)
    return media_out(created)


async def list_media(db, media_type: Optional[MediaType], limit: int, skip: int) -> List[VlogMediaOut]:
    filters = {}
    if media_type:
        filters["media_type"] = media_type
    docs = await vlog_crud.list_media(db, filters, skip, limit)
    return [media_out(doc) for doc in docs]


async def list_chapters(db) -> List[VlogChapterWithEpisodesOut]:
    chapter_docs = await vlog_crud.list_chapters(db, limit=100)
    return [await chapter_with_episodes(db, chapter, public_only=False) for chapter in chapter_docs]


async def create_chapter(db, payload) -> VlogChapterOut:
    now = now_utc()
    data = payload.model_dump()
    data["slug"] = await unique_chapter_slug(db, data["title"], data.get("slug"))
    data["created_at"] = now
    data["updated_at"] = now
    res = await vlog_crud.insert_chapter(db, data)
    created = await vlog_crud.find_chapter_by_id(db, res.inserted_id)
    return chapter_out(created)


async def get_chapter(db, chapter_id: str) -> VlogChapterWithEpisodesOut:
    oid = validate_object_id(chapter_id, "Chapitre ID")
    chapter = await vlog_crud.find_chapter_by_id(db, oid)
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    return await chapter_with_episodes(db, chapter, public_only=False)


async def update_chapter(db, chapter_id: str, payload) -> VlogChapterOut:
    oid = validate_object_id(chapter_id, "Chapitre ID")
    existing = await vlog_crud.find_chapter_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")

    data = payload.model_dump(exclude_unset=True)
    if "title" in data or "slug" in data:
        data["slug"] = await unique_chapter_slug(db, data.get("title", existing["title"]), data.get("slug"), exclude_id=oid)
    data["updated_at"] = now_utc()
    await vlog_crud.update_chapter(db, oid, data)
    updated = await vlog_crud.find_chapter_by_id(db, oid)
    return chapter_out(updated)


async def delete_chapter(db, chapter_id: str, delete_episodes: bool) -> None:
    oid = validate_object_id(chapter_id, "Chapitre ID")
    existing = await vlog_crud.find_chapter_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    await vlog_crud.delete_chapter(db, oid)
    if delete_episodes:
        episode_docs = await vlog_crud.list_episode_ids_by_chapter(db, oid, limit=100)
        episode_ids = [episode["_id"] for episode in episode_docs]
        await vlog_crud.delete_episodes_by_chapter(db, oid)
        if episode_ids:
            await vlog_crud.delete_likes_by_episode_ids(db, episode_ids)
            await vlog_crud.delete_comments_by_episode_ids(db, episode_ids)


async def update_chapter_short_film(db, chapter_id: str, payload) -> VlogChapterOut:
    oid = validate_object_id(chapter_id, "Chapitre ID")
    existing = await vlog_crud.find_chapter_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    await vlog_crud.update_chapter(db, oid, {"short_film": payload.model_dump(), "updated_at": now_utc()})
    updated = await vlog_crud.find_chapter_by_id(db, oid)
    return chapter_out(updated)


async def create_episode(db, chapter_id: str, payload) -> VlogEpisodeOut:
    chapter_oid = validate_object_id(chapter_id, "Chapitre ID")
    if not await vlog_crud.find_chapter_by_id(db, chapter_oid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")

    now = now_utc()
    data = payload.model_dump()
    data["chapter_id"] = chapter_oid
    data["view_count"] = 0
    data["created_at"] = now
    data["updated_at"] = now
    res = await vlog_crud.insert_episode(db, data)
    created = await vlog_crud.find_episode_by_id(db, res.inserted_id)
    return await episode_out(db, created)


async def list_episodes(db, chapter_id: str) -> List[VlogEpisodeOut]:
    chapter_oid = validate_object_id(chapter_id, "Chapitre ID")
    docs = await vlog_crud.list_episodes_by_chapter(db, chapter_oid, limit=50)
    return [await episode_out(db, doc) for doc in docs]


async def update_episode(db, episode_id: str, payload) -> VlogEpisodeOut:
    oid = validate_object_id(episode_id, "Episode ID")
    existing = await vlog_crud.find_episode_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode non trouve")
    data = payload.model_dump(exclude_unset=True)
    data["updated_at"] = now_utc()
    await vlog_crud.update_episode(db, oid, data)
    updated = await vlog_crud.find_episode_by_id(db, oid)
    return await episode_out(db, updated)


async def delete_episode(db, episode_id: str) -> None:
    oid = validate_object_id(episode_id, "Episode ID")
    existing = await vlog_crud.find_episode_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode non trouve")
    await vlog_crud.delete_episode(db, oid)
    await vlog_crud.delete_likes_by_episode(db, oid)
    await vlog_crud.delete_comments_by_episode(db, oid)
