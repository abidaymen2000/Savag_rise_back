import re
from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import vlog as vlog_crud
from app.schemas.vlog import (
    ProductSummary,
    VlogChapterOut,
    VlogChapterWithEpisodesOut,
    VlogEpisodeOut,
    VlogSettingsOut,
)

SETTINGS_COLLECTION = "cms_settings"
VLOG_SETTINGS_KEY = "vlog_page"
CHAPTERS_COLLECTION = "vlog_chapters"
EPISODES_COLLECTION = "vlog_episodes"
MEDIA_COLLECTION = "vlog_media"
LIKES_COLLECTION = "vlog_episode_likes"
COMMENTS_COLLECTION = "vlog_comments"
PUBLIC_CHAPTER_STATUSES = ["coming_soon", "active", "completed"]
PUBLIC_EPISODE_STATUSES = ["coming_soon", "released"]


def now_utc() -> datetime:
    return datetime.utcnow()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "chapter"


def validate_object_id(value: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} invalide")


async def unique_chapter_slug(db, title: str, slug: Optional[str], exclude_id: Optional[ObjectId] = None) -> str:
    base = slugify(slug or title)
    candidate = base
    index = 2
    query: Dict = {"slug": candidate}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    while await vlog_crud.find_chapter_by_slug(db, candidate, exclude_id=exclude_id):
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def chapter_out(doc) -> VlogChapterOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return VlogChapterOut(**payload)


def first_product_image(product: Dict) -> Optional[str]:
    for variant in product.get("variants", []):
        for image in variant.get("images", []):
            if isinstance(image, dict) and image.get("url"):
                return image["url"]
            if isinstance(image, str):
                return image
    return None


async def product_summaries(db, product_ids: List[str]) -> List[ProductSummary]:
    object_ids = []
    for product_id in product_ids:
        try:
            object_ids.append(ObjectId(product_id))
        except Exception:
            continue
    if not object_ids:
        return []

    docs = await vlog_crud.find_products_by_ids(db, object_ids)
    by_id = {str(doc["_id"]): doc for doc in docs}
    summaries = []
    for product_id in product_ids:
        doc = by_id.get(product_id)
        if not doc:
            continue
        summaries.append(ProductSummary(
            id=product_id,
            name=doc["name"],
            full_name=doc.get("full_name"),
            price=doc["price"],
            image_url=first_product_image(doc),
            in_stock=doc.get("in_stock", True),
        ))
    return summaries


async def episode_out(db, doc, current_user: Optional[Dict] = None) -> VlogEpisodeOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    payload["chapter_id"] = str(payload["chapter_id"])
    payload["products"] = await product_summaries(db, payload.get("linked_product_ids", []))
    payload["view_count"] = int(payload.get("view_count", 0) or 0)
    payload["like_count"] = await vlog_crud.count_episode_likes(db, doc["_id"])
    payload["comment_count"] = await vlog_crud.count_visible_episode_comments(db, doc["_id"])
    payload["liked_by_current_user"] = False
    if current_user:
        payload["liked_by_current_user"] = await vlog_crud.find_episode_like(db, doc["_id"], current_user["_id"]) is not None
    return VlogEpisodeOut(**payload)


async def settings_out(db) -> VlogSettingsOut:
    doc = await vlog_crud.find_vlog_settings(db)
    if not doc:
        return VlogSettingsOut()
    return VlogSettingsOut(**doc["value"], updated_at=doc.get("updated_at"))


async def chapter_with_episodes(db, chapter_doc, public_only: bool, current_user: Optional[Dict] = None) -> VlogChapterWithEpisodesOut:
    chapter = chapter_out(chapter_doc).model_dump()
    episode_filter = {"chapter_id": chapter_doc["_id"]}
    if public_only:
        episode_filter["status"] = {"$in": PUBLIC_EPISODE_STATUSES}
    episode_docs = await vlog_crud.list_chapter_episodes(db, episode_filter, limit=50)
    chapter["episodes"] = [await episode_out(db, episode, current_user=current_user) for episode in episode_docs]
    return VlogChapterWithEpisodesOut(**chapter)
