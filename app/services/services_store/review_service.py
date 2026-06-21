import datetime
from typing import List, Optional

from fastapi import HTTPException, Request, status

from app.analytics.service import track_event
from app.crud import review as review_crud
from app.schemas.review import ReviewOut


async def attach_author(db, doc: dict) -> dict:
    user = None
    try:
        user = await review_crud.find_user_author(db, doc.get("user_id"))
    except Exception:
        user = None

    doc["author"] = (user or {}).get("full_name") or (user or {}).get("email") or "Utilisateur"
    doc["status"] = doc.get("status", "visible")
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
    return doc


async def add_review(db, product_id: str, payload, request: Request, current_user) -> ReviewOut:
    data = payload.dict(exclude_none=True)
    data["user_id"] = str(current_user.get("_id"))
    doc = await review_crud.create_review(db, product_id, data)
    await track_event(
        db,
        "review_created",
        user_id=str(current_user.get("_id")),
        product_id=product_id,
        metadata={"rating": getattr(payload, "rating", None)},
        request=request,
    )
    return ReviewOut(**await attach_author(db, doc))


async def list_reviews(db, product_id: str, rating: Optional[int], skip: int, limit: int, sort_best: bool) -> List[ReviewOut]:
    docs = await review_crud.list_reviews(db, product_id, rating, skip, limit, sort_best)
    return [ReviewOut(**await attach_author(db, doc)) for doc in docs]


async def get_review_stats(db, product_id: str):
    return await review_crud.get_review_stats(db, product_id)


async def list_my_reviews(db, current_user, skip: int, limit: int) -> List[ReviewOut]:
    docs = await review_crud.list_user_reviews(db, str(current_user.get("_id")), skip, limit)
    return [ReviewOut(**await attach_author(db, doc)) for doc in docs]


async def get_review(db, product_id: str, review_id: str) -> ReviewOut:
    doc = await review_crud.get_review(db, product_id, review_id)
    if not doc or doc.get("status") == "hidden":
        raise HTTPException(404, "Avis non trouve")
    return ReviewOut(**await attach_author(db, doc))


async def update_my_review(db, product_id: str, review_id: str, payload, current_user) -> ReviewOut:
    doc = await review_crud.get_review(db, product_id, review_id)
    if not doc:
        raise HTTPException(404, "Avis non trouve")
    if str(doc["user_id"]) != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisee")

    data = {k: v for k, v in payload.dict().items() if v is not None}
    data["updated_at"] = datetime.datetime.utcnow()
    updated = await review_crud.update_review(db, product_id, review_id, data)
    return ReviewOut(**await attach_author(db, updated))


async def delete_my_review(db, product_id: str, review_id: str, current_user) -> None:
    doc = await review_crud.get_review(db, product_id, review_id)
    if not doc:
        raise HTTPException(404, "Avis non trouve")
    if str(doc["user_id"]) != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisee")
    await review_crud.delete_review(db, product_id, review_id)
