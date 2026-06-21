from typing import Optional

from fastapi import HTTPException, status

from app.crud import review as review_crud
from app.crud import vlog as vlog_crud
from app.schemas.review import PaginatedReviewsOut, ReviewOut
from app.schemas.vlog import PaginatedVlogCommentsOut, VlogCommentOut
from app.services.services_cms.vlog_service import now_utc, validate_object_id


async def comment_out(db, doc) -> VlogCommentOut:
    user = await vlog_crud.find_user_summary(db, doc["user_id"])
    episode = await vlog_crud.find_episode_summary(db, doc["episode_id"])
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


async def review_out(db, doc) -> ReviewOut:
    user = None
    try:
        user = await review_crud.find_user_author(db, doc.get("user_id"))
    except Exception:
        user = None

    product = None
    try:
        product = await review_crud.find_product_summary(db, doc.get("product_id"))
    except Exception:
        product = None

    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    payload["status"] = payload.get("status", "visible")
    payload["author"] = (user or {}).get("full_name") or (user or {}).get("email") or "Utilisateur"
    payload["product_name"] = (product or {}).get("full_name") or (product or {}).get("name")
    return ReviewOut(**payload)


async def list_comments(
    db,
    page: int,
    page_size: int,
    status_filter,
    episode_id: Optional[str],
    user_id: Optional[str],
    q: Optional[str],
) -> PaginatedVlogCommentsOut:
    filters = {}
    if status_filter:
        filters["status"] = status_filter
    if episode_id:
        filters["episode_id"] = validate_object_id(episode_id, "Episode ID")
    if user_id:
        filters["user_id"] = validate_object_id(user_id, "Utilisateur ID")
    if q:
        filters["content"] = {"$regex": q, "$options": "i"}

    skip = (page - 1) * page_size
    total = await vlog_crud.count_comments(db, filters)
    docs = await vlog_crud.list_comments(db, filters, skip, page_size)
    return PaginatedVlogCommentsOut(
        items=[await comment_out(db, doc) for doc in docs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


async def list_product_reviews(
    db,
    page: int,
    page_size: int,
    status_filter,
    product_id: Optional[str],
    user_id: Optional[str],
    rating: Optional[int],
    q: Optional[str],
) -> PaginatedReviewsOut:
    filters = {}
    if status_filter == "visible":
        filters["status"] = {"$ne": "hidden"}
    elif status_filter == "hidden":
        filters["status"] = "hidden"
    if product_id:
        filters["product_id"] = product_id
    if user_id:
        filters["user_id"] = user_id
    if rating:
        filters["rating"] = rating
    if q:
        filters["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"comment": {"$regex": q, "$options": "i"}},
        ]

    skip = (page - 1) * page_size
    total = await review_crud.count_reviews(db, filters)
    docs = await review_crud.list_reviews_by_filters(db, filters, skip, page_size)
    return PaginatedReviewsOut(
        items=[await review_out(db, doc) for doc in docs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


async def update_product_review(db, review_id: str, payload) -> ReviewOut:
    oid = validate_object_id(review_id, "Avis ID")
    existing = await review_crud.find_review_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avis non trouve")

    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        data["title"] = data["title"].strip()
    if "comment" in data and data["comment"] is not None:
        data["comment"] = data["comment"].strip()
    data["updated_at"] = now_utc()
    await review_crud.update_review_by_id(db, oid, data)
    updated = await review_crud.find_review_by_id(db, oid)
    return await review_out(db, updated)


async def delete_product_review(db, review_id: str) -> None:
    oid = validate_object_id(review_id, "Avis ID")
    existing = await review_crud.find_review_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avis non trouve")
    await review_crud.delete_review_by_id(db, oid)


async def update_comment(db, comment_id: str, payload) -> VlogCommentOut:
    oid = validate_object_id(comment_id, "Commentaire ID")
    existing = await vlog_crud.find_comment_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commentaire non trouve")

    data = payload.model_dump(exclude_unset=True)
    if "content" in data:
        data["content"] = data["content"].strip()
        if not data["content"]:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Commentaire vide")
    data["updated_at"] = now_utc()
    await vlog_crud.update_comment(db, oid, data)
    updated = await vlog_crud.find_comment_by_id(db, oid)
    return await comment_out(db, updated)


async def delete_comment(db, comment_id: str) -> None:
    oid = validate_object_id(comment_id, "Commentaire ID")
    existing = await vlog_crud.find_comment_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commentaire non trouve")
    await vlog_crud.delete_comment(db, oid)
