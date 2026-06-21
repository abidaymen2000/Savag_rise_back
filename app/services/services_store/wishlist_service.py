from typing import List

from fastapi import Request

from app.analytics.service import track_event
from app.crud import wishlist as wishlist_crud
from app.schemas.wishlist import WishlistOut


def wishlist_out(doc) -> WishlistOut:
    return WishlistOut(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        product_id=str(doc["product_id"]),
        added_at=doc["added_at"],
    )


async def add_wishlist_item(db, payload, request: Request, current_user) -> WishlistOut:
    user_id = str(current_user["_id"])
    doc = await wishlist_crud.add_to_wishlist(db, user_id, payload.product_id)
    await track_event(db, "wishlist_added", user_id=user_id, product_id=payload.product_id, request=request)
    return wishlist_out(doc)


async def remove_wishlist_item(db, product_id: str, request: Request, current_user) -> None:
    user_id = str(current_user["_id"])
    await wishlist_crud.remove_from_wishlist(db, user_id, product_id)
    await track_event(db, "wishlist_removed", user_id=user_id, product_id=product_id, request=request)


async def list_wishlist(db, current_user, skip: int, limit: int) -> List[WishlistOut]:
    docs = await wishlist_crud.list_wishlist(db, str(current_user["_id"]), skip, limit)
    return [wishlist_out(doc) for doc in docs]
