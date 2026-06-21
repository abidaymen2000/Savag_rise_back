from typing import List

from fastapi import HTTPException, Request, status

from app.analytics.service import track_event
from app.crud import vlog as vlog_crud
from app.schemas.vlog import (
    VlogChapterWithEpisodesOut,
    VlogCommentOut,
    VlogEpisodeLikeOut,
    VlogEpisodeViewOut,
    VlogPageOut,
)
from app.services.services_cms.engagement_service import comment_out
from app.services.services_cms.vlog_service import (
    PUBLIC_CHAPTER_STATUSES,
    PUBLIC_EPISODE_STATUSES,
    chapter_with_episodes,
    now_utc,
    settings_out,
    validate_object_id,
)


async def public_episode_or_404(db, episode_id: str):
    oid = validate_object_id(episode_id, "Episode ID")
    episode = await vlog_crud.find_public_episode(db, oid, PUBLIC_EPISODE_STATUSES)
    if not episode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode non trouve")
    return episode


async def read_storefront_vlog(db, current_user) -> VlogPageOut:
    settings = await settings_out(db)
    if not settings.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page vlog desactivee")

    chapter_docs = await vlog_crud.list_chapters(db, {"status": {"$in": PUBLIC_CHAPTER_STATUSES}}, limit=100)
    chapters = [
        await chapter_with_episodes(db, chapter, public_only=True, current_user=current_user)
        for chapter in chapter_docs
    ]
    return VlogPageOut(settings=settings, chapters=chapters)


async def read_storefront_vlog_chapter(db, slug: str, current_user) -> VlogChapterWithEpisodesOut:
    chapter = await vlog_crud.find_chapter(db, {
        "slug": slug,
        "status": {"$in": PUBLIC_CHAPTER_STATUSES},
    })
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    return await chapter_with_episodes(db, chapter, public_only=True, current_user=current_user)


async def track_episode_view(db, episode_id: str, request: Request, current_user) -> VlogEpisodeViewOut:
    episode = await public_episode_or_404(db, episode_id)
    updated = await vlog_crud.increment_episode_view_count(db, episode["_id"], now_utc())
    await track_event(
        db,
        "vlog_episode_viewed",
        user_id=str(current_user["_id"]) if current_user else None,
        metadata={
            "episode_id": str(episode["_id"]),
            "chapter_id": str(episode.get("chapter_id")) if episode.get("chapter_id") else None,
            "title": episode.get("title"),
        },
        request=request,
    )
    return VlogEpisodeViewOut(
        episode_id=str(episode["_id"]),
        view_count=int((updated or episode).get("view_count", 0) or 0),
    )


async def like_episode(db, episode_id: str, current_user) -> VlogEpisodeLikeOut:
    episode = await public_episode_or_404(db, episode_id)
    await vlog_crud.upsert_episode_like(db, episode["_id"], current_user["_id"], now_utc())
    like_count = await vlog_crud.count_episode_likes(db, episode["_id"])
    return VlogEpisodeLikeOut(episode_id=str(episode["_id"]), liked=True, like_count=like_count)


async def unlike_episode(db, episode_id: str, current_user) -> VlogEpisodeLikeOut:
    episode = await public_episode_or_404(db, episode_id)
    await vlog_crud.delete_episode_like(db, episode["_id"], current_user["_id"])
    like_count = await vlog_crud.count_episode_likes(db, episode["_id"])
    return VlogEpisodeLikeOut(episode_id=str(episode["_id"]), liked=False, like_count=like_count)


async def create_episode_comment(db, episode_id: str, payload, current_user) -> VlogCommentOut:
    episode = await public_episode_or_404(db, episode_id)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Commentaire vide")
    now = now_utc()
    data = {
        "episode_id": episode["_id"],
        "user_id": current_user["_id"],
        "content": content,
        "status": "visible",
        "created_at": now,
        "updated_at": now,
    }
    res = await vlog_crud.insert_comment(db, data)
    created = await vlog_crud.find_comment_by_id(db, res.inserted_id)
    return await comment_out(db, created)


async def list_episode_comments(db, episode_id: str, skip: int, limit: int) -> List[VlogCommentOut]:
    episode = await public_episode_or_404(db, episode_id)
    docs = await vlog_crud.list_visible_episode_comments(db, episode["_id"], skip, limit)
    return [await comment_out(db, doc) for doc in docs]


async def delete_own_episode_comment(db, episode_id: str, comment_id: str, current_user) -> None:
    episode = await public_episode_or_404(db, episode_id)
    comment_oid = validate_object_id(comment_id, "Commentaire ID")
    doc = await vlog_crud.find_comment_for_episode(db, comment_oid, episode["_id"])
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commentaire non trouve")
    if str(doc["user_id"]) != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisee")
    await vlog_crud.delete_comment(db, comment_oid)
