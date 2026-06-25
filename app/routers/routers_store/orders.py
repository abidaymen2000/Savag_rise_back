from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Path, Request, status

from app.db import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.schemas.order import OrderActionReasonIn, OrderCreate, OrderOut, OrderQuoteOut
from app.services.services_store import order_service


router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "/quote",
    response_model=OrderQuoteOut,
    summary="Calculer les totaux commande sans reserver stock ni promo",
)
async def api_quote_order(
    order_in: OrderCreate,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await order_service.quote_order(db, order_in, request, current_user)


@router.post(
    "/",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Idempotency-Key manquant ou payload invalide"},
        409: {"description": "Conflit d'idempotence: payload different ou requete deja en cours"},
    },
)
async def api_create_order(
    order_in: OrderCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    idempotency_key: Annotated[str, Header(..., alias="Idempotency-Key", description="Cle d'idempotence obligatoire pour la creation de commande")],
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    return await order_service.create_order(db, order_in, background_tasks, request, current_user, idempotency_key)


@router.patch(
    "/{order_id}/cancel",
    response_model=OrderOut,
    status_code=status.HTTP_200_OK,
    summary="Permet au client d'annuler sa commande si elle est encore en pending",
)
async def api_cancel_order(
    background_tasks: BackgroundTasks,
    order_id: str = Path(..., description="ID de la commande a annuler"),
    payload: OrderActionReasonIn | None = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await order_service.cancel_order(db, order_id, background_tasks, current_user, getattr(payload, "reason", None))
