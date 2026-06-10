from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.schemas.vlog import VlogChapterWithEpisodesOut, VlogPageOut
from app.utils.vlog_service import (
    CHAPTERS_COLLECTION,
    PUBLIC_CHAPTER_STATUSES,
    chapter_with_episodes,
    settings_out,
)

router = APIRouter(prefix="/storefront/vlog", tags=["storefront-vlog"])


@router.get("", response_model=VlogPageOut)
async def read_storefront_vlog(db=Depends(get_db)):
    settings = await settings_out(db)
    if not settings.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page vlog desactivee")

    chapter_docs = await db[CHAPTERS_COLLECTION].find(
        {"status": {"$in": PUBLIC_CHAPTER_STATUSES}}
    ).sort("order", 1).to_list(length=100)
    chapters = [await chapter_with_episodes(db, chapter, public_only=True) for chapter in chapter_docs]
    return VlogPageOut(settings=settings, chapters=chapters)


@router.get("/chapters/{slug}", response_model=VlogChapterWithEpisodesOut)
async def read_storefront_vlog_chapter(slug: str, db=Depends(get_db)):
    chapter = await db[CHAPTERS_COLLECTION].find_one({
        "slug": slug,
        "status": {"$in": PUBLIC_CHAPTER_STATUSES},
    })
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre non trouve")
    return await chapter_with_episodes(db, chapter, public_only=True)
