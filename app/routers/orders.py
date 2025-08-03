# app/routers/orders.py
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query, Path
from typing import List
from bson import ObjectId
from jinja2 import Environment, FileSystemLoader

from app.crud.variant import decrement_variant_stock, increment_variant_stock
from app.dependencies import get_current_user
from app.utils.email import send_email

from ..db import get_db
from ..crud.order import create_order as crud_create_order, get_order, update_order_status, mark_paid
from ..schemas.order import OrderCreate, OrderOut
from ..config import settings

router = APIRouter(prefix="/orders", tags=["orders"])

jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True
)

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
    # 1) Décrémente le stock
    for it in order_in.items:
        await decrement_variant_stock(
            db,
            ObjectId(it.product_id),
            it.color,
            it.size,
            it.qty
        )

    # 2) Crée la commande en base
    data = order_in.dict(exclude={"user_id"})
    data["user_id"] = str(current_user["_id"])
    new_order = await crud_create_order(db, data)

    # 3) Prépare order_data pour les templates
    order_data = {
        "id": new_order["id"],
        "date": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
        "user_email": current_user["email"],
        "items": [
            {
                "product_id": it["product_id"],
                "name": (await db["products"]
                             .find_one({"_id": ObjectId(it["product_id"])}, {"full_name": 1}))
                             ["full_name"],
                "color": it["color"],
                "size": it["size"],
                "qty": it["qty"],
                "unit_price": it["unit_price"],
            }
            for it in new_order["items"]
        ],
        "total_amount": new_order["total_amount"],
        "shipping": new_order["shipping"],
    }

    # 4) Rendu HTML + texte brut pour le client
    tpl_client = jinja_env.get_template("order_confirmation.html")
    html_client = tpl_client.render(
        order=order_data,
        logo_url=settings.LOGO_URL,
        support_email=settings.ADMIN_EMAIL
    )

    text_lines = [
        f"Commande #{order_data['id']} - {order_data['date']}",
        "Articles :"
    ]
    for it in order_data["items"]:
        text_lines.append(
            f" - {it['qty']}× {it['name']} ({it['color']}/{it['size']}): "
            f"{it['qty'] * it['unit_price']:.2f}€"
        )
    text_lines += [
        f"Total : {order_data['total_amount']:.2f} €",
        "",
        "Adresse de livraison :",
        order_data["shipping"]["full_name"],
        order_data["shipping"]["address_line1"],
        order_data["shipping"].get("address_line2", ""),
        f"{order_data['shipping']['postal_code']} {order_data['shipping']['city']}",
        order_data["shipping"]["country"],
    ]
    text_client = "\n".join(text_lines)

    background_tasks.add_task(
        send_email,
        subject=f"Votre commande #{order_data['id']} – Savage Rise",
        recipient=current_user["email"],
        body=text_client,
        html=html_client
    )

    # 5) Rendu HTML + texte brut pour l’admin
    tpl_admin = jinja_env.get_template("order_notification_admin.html")
    html_admin = tpl_admin.render(
        order=order_data,
        logo_url=settings.LOGO_URL,
        admin_panel_url=settings.FRONTEND_URL
    )

    text_admin = "\n".join([
        f"Nouvelle commande #{order_data['id']} par {order_data['user_email']}",
        "",
        *[
            f"- {it['qty']}× {it['name']} ({it['color']}/{it['size']}): "
            f"{it['qty'] * it['unit_price']:.2f}€"
            for it in order_data["items"]
        ],
        "",
        f"Total : {order_data['total_amount']:.2f} €",
        "",
        "Adresse de livraison :",
        order_data["shipping"]["full_name"],
        order_data["shipping"]["address_line1"],
        order_data["shipping"].get("address_line2", ""),
        f"{order_data['shipping']['postal_code']} {order_data['shipping']['city']}",
        order_data["shipping"]["country"],
    ])

    background_tasks.add_task(
        send_email,
        subject=f"Nouvelle commande #{order_data['id']}",
        recipient=settings.ADMIN_EMAIL,
        body=text_admin,
        html=html_admin
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
    if ord_doc["user_id"] != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez annuler que vos propres commandes")
    if ord_doc["status"] != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Commande non annulable (statut ≠ pending)")

    # 1) RESTAURATION DU STOCK
    for it in ord_doc["items"]:
        await increment_variant_stock(
            db,
            it["product_id"],
            it["color"],
            it["size"],
            it["qty"]
        )

    # 2) PASSAGE EN STATUS 'cancelled'
    await update_order_status(db, oid, "cancelled")

    # 3) RENVOI DE LA COMMANDE À JOUR
    updated = await get_order(db, oid)
    return updated
