from typing import List

from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import order as order_crud
from app.crud import review as review_crud
from app.crud import users as user_crud
from app.schemas.order import OrderOut
from app.schemas.review import ReviewOut
from app.schemas.user import UserOut


def user_out(user: dict) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        email=user["email"],
        full_name=user.get("full_name"),
        is_active=user["is_active"],
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at"),
    )


def parse_oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID invalide")


async def read_profile(current_user) -> UserOut:
    return user_out(current_user)


async def list_reviews(db, current_user, skip: int, limit: int) -> List[ReviewOut]:
    docs = await review_crud.list_user_reviews(db, str(current_user.get("_id")), skip, limit)
    return [ReviewOut(**doc, id=str(doc["_id"])) for doc in docs]


async def update_profile(db, data, current_user) -> UserOut:
    update_data = data.dict(exclude_unset=True)
    if "email" in update_data:
        exists = await user_crud.get_user_by_email(db, update_data["email"])
        if exists and str(exists["_id"]) != str(current_user["_id"]):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cet email est deja utilise par un autre compte")
    updated = await user_crud.update_user_profile(db, str(current_user["_id"]), update_data)
    return user_out(updated)


async def change_password(db, payload, current_user):
    ok = await user_crud.change_user_password(db, str(current_user["_id"]), payload.current_password, payload.new_password)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mot de passe actuel incorrect")
    return {"message": "Mot de passe mis a jour avec succes"}


async def list_orders(db, current_user) -> List[OrderOut]:
    orders = await order_crud.get_orders_for_user(db, str(current_user["_id"]))
    for order in orders:
        order["id"] = str(order["_id"])
    return orders


async def get_order(db, order_id: str, current_user) -> OrderOut:
    order = await order_crud.get_order(db, parse_oid(order_id))
    if not order or order.get("user_id") != str(current_user["_id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    order["id"] = str(order["_id"])
    return order
