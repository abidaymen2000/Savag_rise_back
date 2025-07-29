# app/routers/orders.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query, Path
from typing import List
from bson import ObjectId

from app.dependencies import get_current_user
from app.utils.email import send_email

from ..db import get_db
from ..crud.order import create_order as crud_create_order, get_order, update_order_status, mark_paid
from ..crud.products import decrement_variant_stock
from ..schemas.order import OrderCreate, OrderOut
from ..config import settings

router = APIRouter(prefix="/orders", tags=["orders"])


def parse_oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID de commande invalide")


@router.post("/", response_model=OrderOut, status_code=201)
async def api_create_order(
    order_in: OrderCreate,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    # décrémente le stock
    for it in order_in.items:
        await decrement_variant_stock(db, ObjectId(it.product_id), it.color, it.size, it.qty)

    # prépare le payload
    data = order_in.dict()
    data["user_id"] = str(current_user["_id"])

    # création de la commande
    new_order = await crud_create_order(db, data)

    # envoi d’un email à l’admin
    subject = f"Nouvelle commande Savage Rise #{new_order['id']}"
    body_lines = [
        f"ID: {new_order['id']}",
        f"User: {current_user['email']} ({data['user_id']})",
        "",
        "=== Items ==="
    ]
    for it in data["items"]:
        body_lines.append(f"- {it['qty']}× {it['product_id']} | {it['color']} / {it['size']} @ {it['unit_price']}€")
    body_lines += [
        "",
        "=== Shipping ===",
        f"{data['shipping']['full_name']}",
        f"{data['shipping']['address_line1']}",
        f"{data['shipping'].get('address_line2','')}",
        f"{data['shipping']['postal_code']} {data['shipping']['city']}",
        f"{data['shipping']['country']}",
        "",
        f"Total: {new_order['total_amount']}€",
    ]
    background_tasks.add_task(
        send_email,
        subject,
        settings.ADMIN_EMAIL,
        "\n".join(body_lines),
    )

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
