# app/routers/orders.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query, Path
from typing import List
from bson import ObjectId

from app.crud.variant import decrement_variant_stock
from app.dependencies import get_current_user
from app.utils.email import send_email

from ..db import get_db
from ..crud.order import create_order as crud_create_order, get_order, update_order_status, mark_paid
from ..schemas.order import OrderCreate, OrderOut
from ..config import settings

router = APIRouter(prefix="/orders", tags=["orders"])


def parse_oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID de commande invalide")


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def api_create_order(
    order_in: OrderCreate,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 1) On décrémente le stock (ou on lève 400)
    for it in order_in.items:
        prod_oid = ObjectId(it.product_id)
        await decrement_variant_stock(db, prod_oid, it.color, it.size, it.qty)

    # 2) On prépare la donnée et on crée la commande
    data = order_in.dict(exclude={"user_id"})
    data["user_id"] = str(current_user["_id"])
    new_order = await crud_create_order(db, data)

    # 3) On notifie l’admin par email
    subject = f"Nouvelle commande #{new_order['id']}"
    body = [f"Commande {new_order['id']} par {current_user['email']}", "", "Articles :"]
    for it in data["items"]:
        body.append(f"  • {it['qty']}× {it['product_id']} ({it['color']}/{it['size']})")
    body += [
        "",
        "Livraison :",
        f"{data['shipping']['full_name']}",
        f"{data['shipping']['address_line1']}",
        f"{data['shipping'].get('address_line2','')}",
        f"{data['shipping']['postal_code']} {data['shipping']['city']}",
        f"{data['shipping']['country']}",
        "",
        f"Total : {new_order['total_amount']} €"
    ]

    background_tasks.add_task(
        send_email,
        subject,
        settings.ADMIN_EMAIL,
        "\n".join(body)
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


@router.patch(
    "/{order_id}/cancel",
    response_model=OrderOut,
    status_code=status.HTTP_200_OK,
    summary="Permet au client d'annuler sa commande si elle est encore en pending"
)
async def api_cancel_order(
    order_id: str = Path(..., description="ID de la commande à annuler"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    oid = parse_oid(order_id)
    ord_doc = await get_order(db, oid)
    if not ord_doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    # Vérifie que c'est bien la commande du user
    if ord_doc.get("user_id") != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez annuler que vos propres commandes")
    # La seule annulation autorisée est sur les commandes en 'pending'
    if ord_doc.get("status") != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Commande non annulable (statut ≠ pending)")
    # Passe le statut à 'cancelled'
    await update_order_status(db, oid, "cancelled")
    # Retourne la commande à jour
    updated = await get_order(db, oid)
    # Pydantic attend un champ 'id' en string
    updated["id"] = str(updated["_id"])
    return updated