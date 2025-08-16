# app/routers/orders.py
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query, Path
from typing import List, Tuple
from bson import ObjectId
from jinja2 import Environment, FileSystemLoader

from app.crud.variant import decrement_variant_stock, increment_variant_stock
from app.dependencies import get_current_user
from app.utils.email import send_email

from ..db import get_db
from ..crud.order import create_order as crud_create_order, get_order, update_order_status, mark_paid
from ..schemas.order import OrderCreate, OrderOut
from ..config import settings

# === Promo ===
from app.crud import promocodes as promo_crud
from app.utils.discounts import validate_and_compute
# =============

router = APIRouter(prefix="/orders", tags=["orders"])

jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True
)

# === Frais de livraison (même logique que le front) ===
SHIPPING_THRESHOLD = 300
SHIPPING_COST = 7
# ======================================================

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
    user_id = str(current_user["_id"])

    # 1) Calcul des totaux côté serveur (hors livraison)
    subtotal = 0.0
    for it in order_in.items:
        subtotal += it.qty * it.unit_price

    total_amount = subtotal
    discount_value = 0.0
    applied_code = None
    promo_reserved = False

    # 2) Si code promo, on valide ET on réserve l'usage de façon atomique
    if getattr(order_in, "promo_code", None):
        promo = await promo_crud.get_by_code(db, order_in.promo_code)
        if not promo:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code promo invalide")

        valid, reason, discounted_total, discount_val = validate_and_compute(
            promo,
            user_id=user_id,
            order_total=subtotal,
            product_ids=[it.product_id for it in order_in.items],
            category_ids=None,
        )
        if not valid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Code promo refusé: {reason}")

        # Réserver l'usage (respecte per_user_limit, max_uses, dates)
        reserved = await promo_crud.reserve_use(db, promo["code"], user_id)
        if not reserved:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Ce code promo n'est plus disponible ou a déjà été utilisé par ce compte."
            )

        applied_code = promo["code"]
        discount_value = discount_val or 0.0
        total_amount = discounted_total
        promo_reserved = True

    # 2bis) Livraison (calculée côté backend pour cohérence des emails / totals)
    after_discount = total_amount
    shipping_amount = 0 if after_discount >= SHIPPING_THRESHOLD else SHIPPING_COST
    total_amount = after_discount + shipping_amount

    # 3) Décrémenter le stock + créer la commande (avec rollback si erreur)
    decremented: List[Tuple[str, str, str, int]] = []
    try:
        for it in order_in.items:
            await decrement_variant_stock(
                db,
                ObjectId(it.product_id),
                it.color,
                it.size,
                it.qty
            )
            decremented.append((it.product_id, it.color, it.size, it.qty))

        data = order_in.dict(exclude={"user_id"})
        data["user_id"] = user_id
        data["subtotal"] = subtotal
        data["discount_value"] = discount_value
        data["promo_code"] = applied_code
        data["shipping_amount"] = shipping_amount
        data["total_amount"] = total_amount
        if promo_reserved:
            # flag interne pour savoir qu'on a déjà réservé (évite les doubles release)
            data["promo_reserved"] = True

        new_order = await crud_create_order(db, data)

    except Exception:
        # ↩️ rollback stock
        for pid, color, size, qty in reversed(decremented):
            try:
                await increment_variant_stock(db, ObjectId(pid), color, size, qty)
            except Exception:
                pass
        # ↩️ rollback réservation promo si elle existait
        if promo_reserved and applied_code:
            try:
                await promo_crud.release_use(db, applied_code, user_id)
            except Exception:
                pass
        raise

    # 4) Prépare order_data pour les templates (fallback nom produit)
    order_data = {
        "id": new_order["id"],
        "date": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
        "user_email": current_user["email"],
        "items": [
            {
                "product_id": it["product_id"],
                "name": (
                    (await db["products"].find_one(
                        {"_id": ObjectId(it["product_id"])}, {"full_name": 1}
                    )) or {}
                ).get("full_name", it["product_id"]),
                "color": it["color"],
                "size": it["size"],
                "qty": it["qty"],
                "unit_price": it["unit_price"],
            }
            for it in new_order["items"]
        ],
        "total_amount": new_order["total_amount"],
        "shipping": new_order["shipping"],
        "shipping_amount": new_order.get("shipping_amount", 0),
        "subtotal": new_order.get("subtotal"),
        "discount_value": new_order.get("discount_value"),
        "promo_code": new_order.get("promo_code"),
    }

    # 5) E-mail client
    tpl_client = jinja_env.get_template("order_confirmation.html")
    html_client = tpl_client.render(
        order=order_data,
        logo_url=settings.LOGO_URL,
        support_email=settings.ADMIN_EMAIL
    )

    text_lines = [
        f"Commande #{order_data['id']} - {order_data['date']}",
        "Articles :",
        *[
            f" - {it['qty']}× {it['name']} ({it['color']}/{it['size']}): {it['qty'] * it['unit_price']:.2f}TND"
            for it in order_data["items"]
        ]
    ]
    if order_data.get("subtotal") is not None:
        text_lines += [f"Sous-total : {order_data['subtotal']:.2f} TND"]
        if order_data.get("discount_value"):
            label = f"Remise ({order_data['promo_code']})" if order_data.get("promo_code") else "Remise"
            text_lines += [f"{label} : -{order_data['discount_value']:.2f} TND"]
    text_lines += [f"Livraison : {order_data.get('shipping_amount', 0):.2f} TND"]
    text_lines += [
        f"Total : {order_data['total_amount']:.2f} TND",
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

    # 6) E-mail admin
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
            f"- {it['qty']}× {it['name']} ({it['color']}/{it['size']}): {it['qty'] * it['unit_price']:.2f}TND"
            for it in order_data["items"]
        ],
        "",
        *( [f"Sous-total : {order_data['subtotal']:.2f} TND"] if order_data.get("subtotal") is not None else [] ),
        *( [f"Remise ({order_data['promo_code']}) : -{order_data['discount_value']:.2f} TND"]
           if order_data.get("discount_value") else [] ),
        f"Livraison : {order_data.get('shipping_amount', 0):.2f} TND",
        f"Total : {order_data['total_amount']:.2f} TND",
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
    # IMPORTANT: NE PLUS incrémenter ici — l'usage a déjà été "réservé" à la création
    return {"message": "Paiement enregistré"}


@router.patch(
    "/{order_id}/cancel",
    response_model=OrderOut,
    status_code=status.HTTP_200_OK,
    summary="Permet au client d'annuler sa commande si elle est encore en pending"
)
async def api_cancel_order(
    background_tasks: BackgroundTasks,                                  # ⬅️ non-default d'abord
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
            ObjectId(it["product_id"]),
            it["color"],
            it["size"],
            it["qty"]
        )

    # 2) Libérer la réservation du code promo si elle existait
    if ord_doc.get("promo_code"):
        try:
            await promo_crud.release_use(db, ord_doc["promo_code"], ord_doc.get("user_id"))
        except Exception:
            # on n'empêche pas l'annulation si la libération échoue
            pass

    # 3) PASSAGE EN STATUS 'cancelled'
    await update_order_status(db, oid, "cancelled")

    # 4) RECHARGER LA COMMANDE
    updated = await get_order(db, oid)

    # 5) EMAILS : client + admin
    order_data = {
        "id": updated.get("id", str(oid)),
        "date": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
        "user_email": current_user["email"],
        "items": [],
        "total_amount": updated["total_amount"],
        "shipping": updated["shipping"],
        "shipping_amount": updated.get("shipping_amount", 0),
        "subtotal": updated.get("subtotal"),
        "discount_value": updated.get("discount_value"),
        "promo_code": updated.get("promo_code"),
    }

    for it in updated["items"]:
        prod = await db["products"].find_one({"_id": ObjectId(it["product_id"])}, {"full_name": 1})
        order_data["items"].append({
            "product_id": it["product_id"],
            "name": (prod or {}).get("full_name", it["product_id"]),
            "color": it["color"],
            "size": it["size"],
            "qty": it["qty"],
            "unit_price": it["unit_price"],
        })

    # -- Client
    tpl_client = jinja_env.get_template("order_cancellation_client.html")
    html_client = tpl_client.render(
        order=order_data,
        logo_url=settings.LOGO_URL,
        support_email=settings.ADMIN_EMAIL
    )
    text_lines = [
        f"Annulation de votre commande #{order_data['id']} - {order_data['date']}",
        "",
        "Détails des articles annulés :",
        *[
            f"- {it['qty']}× {it['name']} ({it['color']}/{it['size']}): {it['qty']*it['unit_price']:.2f}TND"
            for it in order_data["items"]
        ],
    ]
    if order_data.get("subtotal") is not None:
        text_lines += [f"Sous-total : {order_data['subtotal']:.2f} TND"]
        if order_data.get("discount_value"):
            label = f"Remise ({order_data['promo_code']})" if order_data.get("promo_code") else "Remise"
            text_lines += [f"{label} : -{order_data['discount_value']:.2f} TND"]
    text_lines += [f"Livraison : {order_data.get('shipping_amount', 0):.2f} TND"]
    text_lines += [f"Total : {order_data['total_amount']:.2f} TND"]
    text_client = "\n".join(text_lines)

    background_tasks.add_task(
        send_email,
        subject=f"Commande #{order_data['id']} annulée – Savage Rise",
        recipient=current_user["email"],
        body=text_client,
        html=html_client
    )

    # -- Admin
    tpl_admin = jinja_env.get_template("order_cancellation_admin.html")
    html_admin = tpl_admin.render(
        order=order_data,
        logo_url=settings.LOGO_URL,
        admin_panel_url=settings.FRONTEND_URL
    )
    text_admin_lines = [
        f"Commande annulée #{order_data['id']} par {order_data['user_email']}",
        "",
        *[
            f"- {it['qty']}× {it['name']} ({it['color']}/{it['size']}): {it['qty']*it['unit_price']:.2f}TND"
            for it in order_data["items"]
        ],
        "",
    ]
    if order_data.get("subtotal") is not None:
        text_admin_lines += [f"Sous-total : {order_data['subtotal']:.2f} TND"]
        if order_data.get("discount_value"):
            label = f"Remise ({order_data['promo_code']})" if order_data.get("promo_code") else "Remise"
            text_admin_lines += [f"{label} : -{order_data['discount_value']:.2f} TND"]
    text_admin_lines += [f"Livraison : {order_data.get('shipping_amount', 0):.2f} TND"]
    text_admin_lines += [f"Total : {order_data['total_amount']:.2f} TND"]
    text_admin = "\n".join(text_admin_lines)

    background_tasks.add_task(
        send_email,
        subject=f"Commande annulée #{order_data['id']}",
        recipient=settings.ADMIN_EMAIL,
        body=text_admin,
        html=html_admin
    )

    return updated
