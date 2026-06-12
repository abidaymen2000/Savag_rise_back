from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.db import get_db
from app.dependencies_admin import get_current_admin
from app.schemas.review import AdminReviewUpdate, PaginatedReviewsOut, ReviewOut, ReviewStatus
from app.schemas.vlog import PaginatedVlogCommentsOut, VlogCommentOut, VlogCommentStatus, VlogCommentUpdate
from app.utils.vlog_service import COMMENTS_COLLECTION, EPISODES_COLLECTION, now_utc, validate_object_id

router = APIRouter(prefix="/admin/comments", tags=["admin-comments"])


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


async def _review_out(db, doc) -> ReviewOut:
    user = None
    try:
        user = await db["users"].find_one(
            {"_id": ObjectId(str(doc.get("user_id")))},
            {"full_name": 1, "email": 1},
        )
    except Exception:
        user = None

    product = None
    try:
        product = await db["products"].find_one(
            {"_id": ObjectId(str(doc.get("product_id")))},
            {"name": 1, "full_name": 1},
        )
    except Exception:
        product = None

    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    payload["status"] = payload.get("status", "visible")
    payload["author"] = (user or {}).get("full_name") or (user or {}).get("email") or "Utilisateur"
    payload["product_name"] = (product or {}).get("full_name") or (product or {}).get("name")
    return ReviewOut(**payload)


@router.get("", response_model=PaginatedVlogCommentsOut)
async def admin_list_comments(
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: Optional[VlogCommentStatus] = Query(None, alias="status"),
    episode_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Recherche dans le contenu du commentaire"),
):
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
    total = await db[COMMENTS_COLLECTION].count_documents(filters)
    docs = await db[COMMENTS_COLLECTION].find(filters).sort("created_at", -1).skip(skip).limit(page_size).to_list(length=page_size)
    return PaginatedVlogCommentsOut(
        items=[await _comment_out(db, doc) for doc in docs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/product-reviews", response_model=PaginatedReviewsOut)
async def admin_list_product_reviews(
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: Optional[ReviewStatus] = Query(None, alias="status"),
    product_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    rating: Optional[int] = Query(None, ge=1, le=5),
    q: Optional[str] = Query(None, description="Recherche dans le titre ou commentaire"),
):
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
    total = await db["reviews"].count_documents(filters)
    docs = await db["reviews"].find(filters).sort("created_at", -1).skip(skip).limit(page_size).to_list(length=page_size)
    return PaginatedReviewsOut(
        items=[await _review_out(db, doc) for doc in docs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.patch("/product-reviews/{review_id}", response_model=ReviewOut)
async def admin_update_product_review(
    review_id: str,
    payload: AdminReviewUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(review_id, "Avis ID")
    existing = await db["reviews"].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avis non trouve")

    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        data["title"] = data["title"].strip()
    if "comment" in data and data["comment"] is not None:
        data["comment"] = data["comment"].strip()
    data["updated_at"] = now_utc()
    await db["reviews"].update_one({"_id": oid}, {"$set": data})
    updated = await db["reviews"].find_one({"_id": oid})
    return await _review_out(db, updated)


@router.delete("/product-reviews/{review_id}", status_code=204)
async def admin_delete_product_review(
    review_id: str,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(review_id, "Avis ID")
    existing = await db["reviews"].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avis non trouve")
    await db["reviews"].delete_one({"_id": oid})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{comment_id}", response_model=VlogCommentOut)
async def admin_update_comment(
    comment_id: str,
    payload: VlogCommentUpdate,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(comment_id, "Commentaire ID")
    existing = await db[COMMENTS_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commentaire non trouve")

    data = payload.model_dump(exclude_unset=True)
    if "content" in data:
        data["content"] = data["content"].strip()
        if not data["content"]:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Commentaire vide")
    data["updated_at"] = now_utc()
    await db[COMMENTS_COLLECTION].update_one({"_id": oid}, {"$set": data})
    updated = await db[COMMENTS_COLLECTION].find_one({"_id": oid})
    return await _comment_out(db, updated)


@router.delete("/{comment_id}", status_code=204)
async def admin_delete_comment(
    comment_id: str,
    _admin=Depends(get_current_admin),
    db=Depends(get_db),
):
    oid = validate_object_id(comment_id, "Commentaire ID")
    existing = await db[COMMENTS_COLLECTION].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commentaire non trouve")
    await db[COMMENTS_COLLECTION].delete_one({"_id": oid})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
