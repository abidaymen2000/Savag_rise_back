from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_current_user, get_db
from app.schemas.review import ReviewCreate, ReviewOut, ReviewStats, ReviewUpdate
from app.services.services_store import review_service


router = APIRouter(
    prefix="/products/{product_id}/reviews",
    tags=["Reviews"]
)


@router.post("/", response_model=ReviewOut, status_code=201)
async def add_review(
    product_id: str,
    payload: ReviewCreate,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    return await review_service.add_review(db, product_id, payload, request, current_user)


@router.get("/", response_model=List[ReviewOut])
async def get_reviews(
    product_id: str,
    rating: Optional[int] = Query(None, ge=1, le=5),
    sort_best: bool = Query(False, description="true pour tri par note desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db)
):
    return await review_service.list_reviews(db, product_id, rating, skip, limit, sort_best)


@router.get("/stats", response_model=ReviewStats)
async def review_stats(
    product_id: str,
    db=Depends(get_db)
):
    return await review_service.get_review_stats(db, product_id)


@router.get("/myreview", response_model=List[ReviewOut], summary="Mes avis")
async def get_my_reviews(
    product_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    return await review_service.list_my_reviews(db, current_user, skip, limit)


@router.get("/{review_id}", response_model=ReviewOut)
async def read_review(product_id: str, review_id: str, db=Depends(get_db)):
    return await review_service.get_review(db, product_id, review_id)


@router.put("/{review_id}", response_model=ReviewOut)
async def edit_review(
    product_id: str,
    review_id: str,
    payload: ReviewUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await review_service.update_my_review(db, product_id, review_id, payload, current_user)


@router.delete("/{review_id}", status_code=204)
async def remove_review(
    product_id: str,
    review_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    await review_service.delete_my_review(db, product_id, review_id, current_user)
