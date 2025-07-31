# app/routers/wishlist.py
from fastapi import APIRouter, Depends, Query
from typing import List
from app.schemas.wishlist import WishlistCreate, WishlistOut
from app.crud.wishlist import add_to_wishlist, remove_from_wishlist, list_wishlist
from app.dependencies import get_db, get_current_user  # dépendance pour récupérer user

router = APIRouter(prefix="/profile/wishlist", tags=["Wishlist"])

@router.post("/", response_model=WishlistOut, status_code=201)
async def add_wish(
    payload: WishlistCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    user_id = str(current_user["_id"])
    # optionnel : vérifier que le produit existe
    doc = await add_to_wishlist(db, user_id, payload.product_id)
    return WishlistOut(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        product_id=str(doc["product_id"]),
        added_at=doc["added_at"]
    )

@router.delete("/{product_id}", status_code=204)
async def remove_wish(
    product_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    user_id = str(current_user["_id"])
    await remove_from_wishlist(db, user_id, product_id)

@router.get("/", response_model=List[WishlistOut])
async def get_wishlist(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    user_id = str(current_user["_id"])
    docs = await list_wishlist(db, user_id, skip, limit)
    return [
        WishlistOut(
            id=str(d["_id"]),
            user_id=str(d["user_id"]),
            product_id=str(d["product_id"]),
            added_at=d["added_at"]
        )
        for d in docs
    ]
