import re
from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

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
    while await db[CHAPTERS_COLLECTION].find_one(query):
        candidate = f"{base}-{index}"
        query["slug"] = candidate
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

    docs = await db["products"].find({"_id": {"$in": object_ids}}).to_list(length=len(object_ids))
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


async def episode_out(db, doc) -> VlogEpisodeOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    payload["chapter_id"] = str(payload["chapter_id"])
    payload["products"] = await product_summaries(db, payload.get("linked_product_ids", []))
    return VlogEpisodeOut(**payload)


async def settings_out(db) -> VlogSettingsOut:
    doc = await db[SETTINGS_COLLECTION].find_one({"_id": VLOG_SETTINGS_KEY})
    if not doc:
        return VlogSettingsOut()
    return VlogSettingsOut(**doc["value"], updated_at=doc.get("updated_at"))


async def chapter_with_episodes(db, chapter_doc, public_only: bool) -> VlogChapterWithEpisodesOut:
    chapter = chapter_out(chapter_doc).model_dump()
    episode_filter = {"chapter_id": chapter_doc["_id"]}
    if public_only:
        episode_filter["status"] = {"$in": PUBLIC_EPISODE_STATUSES}
    episode_docs = await db[EPISODES_COLLECTION].find(episode_filter).sort("order", 1).to_list(length=50)
    chapter["episodes"] = [await episode_out(db, episode) for episode in episode_docs]
    return VlogChapterWithEpisodesOut(**chapter)
