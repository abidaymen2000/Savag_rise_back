# app/routers/profile.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.dependencies import get_current_user
from app.db import get_db
from app.crud.users import update_user_profile, change_user_password, get_user_by_id
from app.crud.order import get_orders_for_user   # à créer si besoin
from app.schemas.user import UserOut, UserUpdate, PasswordChange
from app.schemas.order import OrderOut           # si tu as déjà ce schéma

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=UserOut, summary="Récupérer le profil de l’utilisateur connecté")
async def read_profile(
    current_user=Depends(get_current_user)
):
    # get_current_user renvoie déjà l'objet user (dict)
    return UserOut(
        id=str(current_user["_id"]),
        email=current_user["email"],
        is_active=current_user["is_active"]
    )


@router.patch("/me", response_model=UserOut, summary="Mettre à jour son profil")
async def update_profile(
    data: UserUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    update_data = data.dict(exclude_unset=True)
    # si email est modifié, tu peux vérifier unicité ici
    if "email" in update_data:
        from app.crud.users import get_user_by_email
        exists = await get_user_by_email(db, update_data["email"])
        if exists and str(exists["_id"]) != str(current_user["_id"]):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email déjà utilisé")
    updated = await update_user_profile(db, str(current_user["_id"]), update_data)
    return UserOut(
        id=str(updated["_id"]),
        email=updated["email"],
        is_active=updated["is_active"]
    )


@router.post("/change-password", summary="Changer son mot de passe")
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
    summary="Historique de commandes de l’utilisateur"
)
async def list_my_orders(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    # suppose que tu as une CRUD get_orders_for_user
    orders = await get_orders_for_user(db, str(current_user["_id"]))
    return orders
