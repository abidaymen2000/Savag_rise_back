# app/routers/profile.py

from fastapi import APIRouter, Depends, HTTPException, Query, status, Path
from typing import List
from bson import ObjectId

from app.crud.review import list_user_reviews
from app.dependencies import get_current_user
from app.db import get_db
from app.crud.users import (
    get_user_by_email,
    update_user_profile,
    change_user_password,
)
from app.crud.order import get_order, get_orders_for_user
from app.schemas.review import ReviewOut
from app.schemas.user import UserOut, UserUpdate, PasswordChange
from app.schemas.order import OrderOut

router = APIRouter(prefix="/profile", tags=["profile"])


def parse_oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID invalide")


@router.get(
    "/me",
    response_model=UserOut,
    summary="Récupérer le profil de l’utilisateur connecté"
)
async def read_profile(
    current_user=Depends(get_current_user)
):
    return UserOut(
        id=str(current_user["_id"]),
        email=current_user["email"],
        full_name=current_user.get("full_name"),
        is_active=current_user["is_active"],
    )

@router.get(
    "/reviews",
    response_model=List[ReviewOut],
    summary="Récupérer tous mes avis"
)
async def get_my_reviews(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Retourne la liste des reviews que l’utilisateur connecté
    a publiées, tous produits confondus.
    """
    # current_user est un dict Mongo, on en extrait l’_id
    user_id = str(current_user.get("_id"))
    docs = await list_user_reviews(db, user_id, skip, limit)
    return [
        ReviewOut(**d, id=str(d["_id"]))
        for d in docs
    ]

@router.patch(
    "/me",
    response_model=UserOut,
    summary="Mettre à jour son profil"
)
async def update_profile(
    data: UserUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    update_data = data.dict(exclude_unset=True)

    # Si l'utilisateur change d'email, on vérifie l'unicité
    if "email" in update_data:
        exists = await get_user_by_email(db, update_data["email"])
        if exists and str(exists["_id"]) != str(current_user["_id"]):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cet email est déjà utilisé par un autre compte"
            )

    updated = await update_user_profile(
        db,
        str(current_user["_id"]),
        update_data
    )
    return UserOut(
        id=str(updated["_id"]),
        email=updated["email"],
        is_active=updated["is_active"],
    )


@router.post(
    "/change-password",
    summary="Changer son mot de passe"
)
async def change_password(
    payload: PasswordChange,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    ok = await change_user_password(
        db,
        str(current_user["_id"]),
        payload.current_password,
        payload.new_password
    )
    if not ok:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Mot de passe actuel incorrect"
        )
    return {"message": "Mot de passe mis à jour avec succès"}


@router.get(
    "/orders",
    response_model=List[OrderOut],
    summary="Historique des commandes de l’utilisateur"
)
async def list_my_orders(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    orders = await get_orders_for_user(db, str(current_user["_id"]))
    # On transforme chaque _id en id string
    for o in orders:
        o["id"] = str(o["_id"])
    return orders


@router.get(
    "/orders/{order_id}",
    response_model=OrderOut,
    summary="Récupérer une de ses commandes par son ID"
)
async def profile_get_one_order(
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    oid = parse_oid(order_id)
    ord_doc = await get_order(db, oid)
    if not ord_doc or ord_doc.get("user_id") != str(current_user["_id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    ord_doc["id"] = str(ord_doc["_id"])
    return ord_doc
