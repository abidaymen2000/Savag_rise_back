# app/routers/orders.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from typing import List
from bson import ObjectId

from app.dependencies import get_current_user

from ..db import get_db
from ..crud.order import create_order as crud_create_order, get_order, update_order_status, mark_paid
from ..crud.products import decrement_variant_stock
from ..schemas.order import OrderCreate, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


def parse_oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID de commande invalide")


@router.post(
    "/",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une commande COD et mettre à jour le stock"
)
async def api_create_order(
    order_in: OrderCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 1) On décrémente le stock pour chaque item
    for item in order_in.items:
        prod_oid = parse_oid(item.product_id)
        # décrémente ou lève 400 si stock insuffisant
        await decrement_variant_stock(
            db,
            prod_oid,
            item.color,
            item.size,
            item.qty,
        )

    # 2) On crée ensuite le document de commande
    #    create_order renvoie un dict prêt à retourner
    order_data = order_in.dict()
    order_data["user_id"] = str(current_user["_id"])
    new_order = await crud_create_order(db, order_data)
    return new_order


@router.get(
    "/{order_id}",
    response_model=OrderOut,
    summary="Lire une commande par son ID"
)
async def api_get_order(
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
):
    oid = parse_oid(order_id)
    ord_doc = await get_order(db, oid)
    if not ord_doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    return ord_doc


@router.patch(
    "/{order_id}/status",
    summary="Mettre à jour le statut d'une commande"
)
async def api_update_status(
    order_id: str = Path(..., description="ID de la commande"),
    new_status: str = Query(..., description="Nouveau statut"),
    db=Depends(get_db),
):
    oid = parse_oid(order_id)
    await update_order_status(db, oid, new_status)
    return {"message": "Statut mis à jour"}


@router.patch(
    "/{order_id}/pay",
    summary="Marquer la commande comme payée (COD) ou remboursée",
)
async def api_mark_paid(
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
):
    oid = parse_oid(order_id)
    await mark_paid(db, oid)
    return {"message": "Paiement enregistré"}
