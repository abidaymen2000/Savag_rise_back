from typing import List

from fastapi import APIRouter, Depends, Query, Request, Response, status

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
from app.services.services_store import storefront_vlog_service


router = APIRouter(prefix="/storefront/vlog", tags=["storefront-vlog"])


@router.get("", response_model=VlogPageOut)
async def read_storefront_vlog(
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await storefront_vlog_service.read_storefront_vlog(db, current_user)


@router.get("/chapters/{slug}", response_model=VlogChapterWithEpisodesOut)
async def read_storefront_vlog_chapter(
    slug: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await storefront_vlog_service.read_storefront_vlog_chapter(db, slug, current_user)


@router.post("/episodes/{episode_id}/view", response_model=VlogEpisodeViewOut)
async def track_vlog_episode_view(
    episode_id: str,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await storefront_vlog_service.track_episode_view(db, episode_id, request, current_user)


@router.post("/episodes/{episode_id}/like", response_model=VlogEpisodeLikeOut)
async def like_vlog_episode(
    episode_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await storefront_vlog_service.like_episode(db, episode_id, current_user)


@router.delete("/episodes/{episode_id}/like", response_model=VlogEpisodeLikeOut)
async def unlike_vlog_episode(
    episode_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await storefront_vlog_service.unlike_episode(db, episode_id, current_user)


@router.post("/episodes/{episode_id}/comments", response_model=VlogCommentOut, status_code=201)
async def create_vlog_episode_comment(
    episode_id: str,
    payload: VlogCommentCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await storefront_vlog_service.create_episode_comment(db, episode_id, payload, current_user)


@router.get("/episodes/{episode_id}/comments", response_model=List[VlogCommentOut])
async def list_vlog_episode_comments(
    episode_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    return await storefront_vlog_service.list_episode_comments(db, episode_id, skip, limit)


@router.delete("/episodes/{episode_id}/comments/{comment_id}", status_code=204)
async def delete_own_vlog_episode_comment(
    episode_id: str,
    comment_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    await storefront_vlog_service.delete_own_episode_comment(db, episode_id, comment_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
