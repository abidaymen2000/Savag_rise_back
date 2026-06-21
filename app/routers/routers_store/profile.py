from typing import List

from fastapi import APIRouter, Depends, Path, Query

from app.db import get_db
from app.dependencies import get_current_user
from app.schemas.order import OrderOut
from app.schemas.review import ReviewOut
from app.schemas.user import PasswordChange, UserOut, UserUpdate
from app.services.services_store import profile_service


router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=UserOut, summary="Recuperer le profil de l'utilisateur connecte")
async def read_profile(current_user=Depends(get_current_user)):
    return await profile_service.read_profile(current_user)


@router.get("/reviews", response_model=List[ReviewOut], summary="Recuperer tous mes avis")
async def get_my_reviews(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    return await profile_service.list_reviews(db, current_user, skip, limit)


@router.patch("/me", response_model=UserOut, summary="Mettre a jour son profil")
async def update_profile(data: UserUpdate, db=Depends(get_db), current_user=Depends(get_current_user)):
    return await profile_service.update_profile(db, data, current_user)


@router.post("/change-password", summary="Changer son mot de passe")
async def change_password(payload: PasswordChange, db=Depends(get_db), current_user=Depends(get_current_user)):
    return await profile_service.change_password(db, payload, current_user)


@router.get("/orders", response_model=List[OrderOut], summary="Historique des commandes de l'utilisateur")
async def list_my_orders(db=Depends(get_db), current_user=Depends(get_current_user)):
    return await profile_service.list_orders(db, current_user)


@router.get("/orders/{order_id}", response_model=OrderOut, summary="Recuperer une de ses commandes par son ID")
async def profile_get_one_order(
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await profile_service.get_order(db, order_id, current_user)
