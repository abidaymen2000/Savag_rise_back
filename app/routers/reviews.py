# app/routers/reviews.py
from fastapi import APIRouter, HTTPException, Depends, Query
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
    return ReviewOut(**doc, id=str(doc["_id"]))

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
    return [ ReviewOut(**d, id=str(d["_id"])) for d in docs ]

@router.get("/stats", response_model=ReviewStats)
async def review_stats(
    product_id: str,
    db=Depends(get_db)
):
    return await get_review_stats(db, product_id)

@router.get("/myreview", response_model=List[ReviewOut], summary="Mes avis")
async def get_my_reviews(
    db=Depends(get_db),
    current_user=Depends(get_current_user),  # retourne un dict Mongo
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Retourne tous les reviews créés par l'utilisateur connecté.
    """
    # Récupère l'ID depuis le dict current_user
    user_id = str(current_user.get("_id"))
    docs = await list_user_reviews(db, user_id, skip, limit)
    return [
        ReviewOut(**d, id=str(d["_id"]))
        for d in docs
    ]
@router.get("/{review_id}", response_model=ReviewOut)
async def read_review(product_id: str, review_id: str, db=Depends(get_db)):
    doc = await get_review(db, product_id, review_id)
    if not doc:
        raise HTTPException(404, "Avis non trouvé")
    return ReviewOut(**doc, id=str(doc["_id"]))

@router.put("/{review_id}", response_model=ReviewOut)
async def edit_review(
    product_id: str,
    review_id: str,
    payload: ReviewUpdate,
    db=Depends(get_db)
):
    doc = await update_review(db, product_id, review_id, {k: v for k, v in payload.dict().items() if v is not None})
    if not doc:
        raise HTTPException(404, "Avis non trouvé")
    return ReviewOut(**doc, id=str(doc["_id"]))

@router.delete("/{review_id}", status_code=204)
async def remove_review(product_id: str, review_id: str, db=Depends(get_db)):
    await delete_review(db, product_id, review_id)

