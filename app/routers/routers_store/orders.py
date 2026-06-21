from fastapi import APIRouter, BackgroundTasks, Depends, Path, Request, status

from app.db import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.schemas.order import OrderCreate, OrderOut
from app.services.services_store import order_service


router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/quote", summary="Calculer les totaux commande sans reserver stock ni promo")
async def api_quote_order(
    order_in: OrderCreate,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await order_service.quote_order(db, order_in, request, current_user)


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def api_create_order(
    order_in: OrderCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await order_service.create_order(db, order_in, background_tasks, request, current_user)


@router.patch(
    "/{order_id}/cancel",
    response_model=OrderOut,
    status_code=status.HTTP_200_OK,
    summary="Permet au client d'annuler sa commande si elle est encore en pending",
)
async def api_cancel_order(
    background_tasks: BackgroundTasks,
    order_id: str = Path(..., description="ID de la commande a annuler"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await order_service.cancel_order(db, order_id, background_tasks, current_user)
