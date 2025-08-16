# app/routers/reviews.py
import datetime
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional

from app.schemas.review import ReviewCreate, ReviewOut, ReviewUpdate, ReviewStats
from app.crud.review import (
    create_review, get_review, list_user_reviews, update_review, delete_review,
    list_reviews, get_review_stats
)
from app.dependencies import get_current_user, get_db  # votre dépendance Mongo

router = APIRouter(
    prefix="/products/{product_id}/reviews",
    tags=["Reviews"]
)

# ---------- helper: ajoute le champ 'author' ----------
async def _attach_author(db, doc: dict) -> dict:
    """
    Ajoute doc['author'] = full_name ou email de l'utilisateur,
    avec fallback 'Utilisateur'. Ajoute aussi doc['id'] si présent.
    """
    user = None
    try:
        user = await db["users"].find_one(
            {"_id": ObjectId(str(doc.get("user_id")))},
            {"full_name": 1, "email": 1}
        )
    except Exception:
        user = None

    doc["author"] = (user or {}).get("full_name") or (user or {}).get("email") or "Utilisateur"
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
    return doc
# -----------------------------------------------------


@router.post("/", response_model=ReviewOut, status_code=201)
async def add_review(
    product_id: str,
    payload: ReviewCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Construis ton dict d’insertion à partir du payload
    data = payload.dict(exclude_none=True)
    # Injecte l’ID de l’utilisateur authentifié
    data["user_id"] = str(current_user.get("_id"))
    doc = await create_review(db, product_id, data)
    doc = await _attach_author(db, doc)
    return ReviewOut(**doc)


@router.get("/", response_model=List[ReviewOut])
async def get_reviews(
    product_id: str,
    rating: Optional[int]       = Query(None, ge=1, le=5),
    sort_best: bool             = Query(False, description="true pour tri par note desc"),
    skip: int                   = Query(0, ge=0),
    limit: int                  = Query(10, ge=1, le=100),
    db=Depends(get_db)
):
    docs = await list_reviews(db, product_id, rating, skip, limit, sort_best)
    out: List[ReviewOut] = []
    for d in docs:
        d = await _attach_author(db, d)
        out.append(ReviewOut(**d))
    return out


@router.get("/stats", response_model=ReviewStats)
async def review_stats(
    product_id: str,
    db=Depends(get_db)
):
    return await get_review_stats(db, product_id)


@router.get("/myreview", response_model=List[ReviewOut], summary="Mes avis")
async def get_my_reviews(
    product_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Retourne tous les reviews créés par l'utilisateur connecté.
    """
    user_id = str(current_user.get("_id"))
    docs = await list_user_reviews(db, user_id, skip, limit)
    out: List[ReviewOut] = []
    for d in docs:
        d = await _attach_author(db, d)
        out.append(ReviewOut(**d))
    return out


@router.get("/{review_id}", response_model=ReviewOut)
async def read_review(product_id: str, review_id: str, db=Depends(get_db)):
    doc = await get_review(db, product_id, review_id)
    if not doc:
        raise HTTPException(404, "Avis non trouvé")
    doc = await _attach_author(db, doc)
    return ReviewOut(**doc)


@router.put("/{review_id}", response_model=ReviewOut)
async def edit_review(
    product_id: str,
    review_id: str,
    payload: ReviewUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),        # <-- protège
):
    # 1) récupérer l'avis
    doc = await db["reviews"].find_one({"_id": ObjectId(review_id), "product_id": product_id})
    if not doc:
        raise HTTPException(404, "Avis non trouvé")
    # 2) autorisation
    if str(doc["user_id"]) != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée")

    # 3) update
    data = {k: v for k, v in payload.dict().items() if v is not None}
    data["updated_at"] = datetime.datetime.utcnow()
    await db["reviews"].update_one({"_id": doc["_id"]}, {"$set": data})
    updated = await db["reviews"].find_one({"_id": doc["_id"]})
    updated = await _attach_author(db, updated)
    return ReviewOut(**updated)


@router.delete("/{review_id}", status_code=204)
async def remove_review(
    product_id: str,
    review_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),        # <-- protège
):
    doc = await db["reviews"].find_one({"_id": ObjectId(review_id), "product_id": product_id})
    if not doc:
        raise HTTPException(404, "Avis non trouvé")
    if str(doc["user_id"]) != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action non autorisée")

    await db["reviews"].delete_one({"_id": doc["_id"]})
