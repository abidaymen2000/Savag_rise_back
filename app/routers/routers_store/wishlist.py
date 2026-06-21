from typing import List

from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_current_user, get_db
from app.schemas.wishlist import WishlistCreate, WishlistOut
from app.services.services_store import wishlist_service


router = APIRouter(prefix="/profile/wishlist", tags=["Wishlist"])


@router.post("/", response_model=WishlistOut, status_code=201)
async def add_wish(
    payload: WishlistCreate,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await wishlist_service.add_wishlist_item(db, payload, request, current_user)


@router.delete("/{product_id}", status_code=204)
async def remove_wish(
    product_id: str,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    await wishlist_service.remove_wishlist_item(db, product_id, request, current_user)


@router.get("/", response_model=List[WishlistOut])
async def get_wishlist(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await wishlist_service.list_wishlist(db, current_user, skip, limit)
