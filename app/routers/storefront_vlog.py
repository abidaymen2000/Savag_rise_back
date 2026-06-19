from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.analytics.service import track_event
from app.db import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.schemas.vlog import (
    VlogChapterWithEpisodesOut,
    VlogCommentCreate,
    VlogCommentOut,
    VlogEpisodeLikeOut,
    VlogEpisodeViewOut,
    VlogPageOut,
)
from app.utils.vlog_service import (
    CHAPTERS_COLLECTION,
    COMMENTS_COLLECTION,
    EPISODES_COLLECTION,
    LIKES_COLLECTION,
    PUBLIC_CHAPTER_STATUSES,
    PUBLIC_EPISODE_STATUSES,
    chapter_with_episodes,
    now_utc,
    settings_out,
    validate_object_id,
)

router = APIRouter(prefix="/storefront/vlog", tags=["storefront-vlog"])


async def _public_episode_or_404(db, episode_id: str):
    oid = validate_object_id(episode_id, "Episode ID")
    episode = await db[EPISODES_COLLECTION].find_one({
        "_id": oid,
        "status": {"$in": PUBLIC_EPISODE_STATUSES},
    })
    if not episode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode non trouve")
    return episode


async def _comment_out(db, doc) -> VlogCommentOut:
    user = await db["users"].find_one(
        {"_id": doc["user_id"]},
        {"full_name": 1, "email": 1},
    )
    episode = await db[EPISODES_COLLECTION].find_one(
        {"_id": doc["episode_id"]},
        {"title": 1},
    )
    return VlogCommentOut(
        id=str(doc["_id"]),
        episode_id=str(doc["episode_id"]),
        user_id=str(doc["user_id"]),
        content=doc["content"],
        status=doc.get("status", "visible"),
        author=(user or {}).get("full_name") or (user or {}).get("email") or "Utilisateur",
        episode_title=(episode or {}).get("title"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.get("", response_model=VlogPageOut)
async def read_storefront_vlog(
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    settings = await settings_out(db)
    if not settings.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page vlog desactivee")

    chapter_docs = await db[CHAPTERS_COLLECTION].find(
        {"status": {"$in": PUBLIC_CHAPTER_STATUSES}}
    ).sort("order", 1).to_list(length=100)
    chapters = [
        await chapter_with_episodes(db, chapter, public_only=True, current_user=current_user)
        for chapter in chapter_docs
    ]
    return VlogPageOut(settings=settings, chapters=chapters)


@router.get("/chapters/{slug}", response_model=VlogChapterWithEpisodesOut)
async def read_storefront_vlog_chapter(
    slug: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    chapter = await db[CHAPTERS_COLLECTION].find_one({
        "slug": slug,
        "status": {"$in": PUBLIC_CHAPTER_STATUSES},
    })
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    return await chapter_with_episodes(db, chapter, public_only=True, current_user=current_user)


@router.post("/episodes/{episode_id}/view", response_model=VlogEpisodeViewOut)
async def track_vlog_episode_view(
    episode_id: str,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    episode = await _public_episode_or_404(db, episode_id)
    res = await db[EPISODES_COLLECTION].find_one_and_update(
        {"_id": episode["_id"]},
        {"$inc": {"view_count": 1}, "$set": {"updated_at": now_utc()}},
        return_document=True,
    )
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
        view_count=int((res or episode).get("view_count", 0) or 0),
    )


@router.post("/episodes/{episode_id}/like", response_model=VlogEpisodeLikeOut)
async def like_vlog_episode(
    episode_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    episode = await _public_episode_or_404(db, episode_id)
    now = now_utc()
    await db[LIKES_COLLECTION].update_one(
        {"episode_id": episode["_id"], "user_id": current_user["_id"]},
        {"$setOnInsert": {
            "episode_id": episode["_id"],
            "user_id": current_user["_id"],
            "created_at": now,
        }},
        upsert=True,
    )
    like_count = await db[LIKES_COLLECTION].count_documents({"episode_id": episode["_id"]})
    return VlogEpisodeLikeOut(episode_id=str(episode["_id"]), liked=True, like_count=like_count)


@router.delete("/episodes/{episode_id}/like", response_model=VlogEpisodeLikeOut)
async def unlike_vlog_episode(
    episode_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    episode = await _public_episode_or_404(db, episode_id)
    await db[LIKES_COLLECTION].delete_one({
        "episode_id": episode["_id"],
        "user_id": current_user["_id"],
    })
    like_count = await db[LIKES_COLLECTION].count_documents({"episode_id": episode["_id"]})
    return VlogEpisodeLikeOut(episode_id=str(episode["_id"]), liked=False, like_count=like_count)


@router.post("/episodes/{episode_id}/comments", response_model=VlogCommentOut, status_code=201)
async def create_vlog_episode_comment(
    episode_id: str,
    payload: VlogCommentCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    episode = await _public_episode_or_404(db, episode_id)
    now = now_utc()
    data = {
        "episode_id": episode["_id"],
        "user_id": current_user["_id"],
        "content": payload.content.strip(),
        "status": "visible",
        "created_at": now,
        "updated_at": now,
    }
    if not data["content"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Commentaire vide")
    res = await db[COMMENTS_COLLECTION].insert_one(data)
    created = await db[COMMENTS_COLLECTION].find_one({"_id": res.inserted_id})
    return await _comment_out(db, created)


@router.get("/episodes/{episode_id}/comments", response_model=List[VlogCommentOut])
async def list_vlog_episode_comments(
    episode_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    episode = await _public_episode_or_404(db, episode_id)
    docs = await db[COMMENTS_COLLECTION].find({
        "episode_id": episode["_id"],
        "status": "visible",
    }).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return [await _comment_out(db, doc) for doc in docs]


@router.delete("/episodes/{episode_id}/comments/{comment_id}", status_code=204)
async def delete_own_vlog_episode_comment(
    episode_id: str,
    comment_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    episode = await _public_episode_or_404(db, episode_id)
    comment_oid = validate_object_id(comment_id, "Commentaire ID")
    doc = await db[COMMENTS_COLLECTION].find_one({
        "_id": comment_oid,
        "episode_id": episode["_id"],
    })
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commentaire non trouve")
    if str(doc["user_id"]) != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisee")
    await db[COMMENTS_COLLECTION].delete_one({"_id": comment_oid})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
