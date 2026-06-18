# app/routers/orders.py
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query, Path, Request
from typing import List, Tuple
from bson import ObjectId
from jinja2 import Environment, FileSystemLoader

from app.analytics.service import track_event
from app.crud.variant import decrement_variant_stock, increment_variant_stock
from app.crud.shipping_rate import resolve_shipping_rate
from app.dependencies import get_current_user, get_current_user_optional
from app.dependencies_admin import require_permission
from app.utils.email import send_email

from ..db import get_db
from ..crud.order import create_order as crud_create_order, get_order, update_order_status, mark_paid
from ..schemas.order import OrderCreate, OrderOut
from ..config import settings

# === Promo ===
from app.crud import promocodes as promo_crud
from app.utils.discounts import validate_and_compute
from app.utils.pack_service import calculate_order_packs
from app.utils.loyalty_service import (
    award_points_for_paid_order,
    calculate_redeem,
    get_points_balance,
    loyalty_settings_out,
    redeem_points_for_order,
    refund_redeemed_points,
)
# =============

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


@router.post("/quote", summary="Calculer les totaux commande sans reserver stock ni promo")
async def api_quote_order(
    order_in: OrderCreate,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    user_id = str(current_user["_id"]) if current_user else None
    await track_event(
        db,
        "checkout_started",
        user_id=user_id,
        metadata={
            "items_count": len(order_in.items) + len(getattr(order_in, "pack_items", []) or []),
            "payment_method": order_in.payment_method,
            "has_promo_code": bool(getattr(order_in, "promo_code", None)),
        },
        request=request,
    )
    subtotal = sum(it.qty * it.unit_price for it in order_in.items)
    pack_calculation = await calculate_order_packs(db, getattr(order_in, "pack_items", []))
    subtotal += pack_calculation["original_subtotal"]
    pack_discount_value = pack_calculation["discount_value"]
    total_after_discounts = max(0.0, subtotal - pack_discount_value)
    discount_value = pack_discount_value
    promo_discount_value = 0.0
    applied_code = None
    purchasable_items = list(order_in.items) + pack_calculation["expanded_items"]

    if getattr(order_in, "promo_code", None):
        if not current_user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Connectez-vous pour utiliser un code promo.")
        promo = await promo_crud.get_by_code(db, order_in.promo_code)
        if not promo:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code promo invalide")
        valid, reason, discounted_total, promo_discount_value = validate_and_compute(
            promo,
            user_id=user_id,
            order_total=total_after_discounts,
            product_ids=[it.product_id if hasattr(it, "product_id") else it["product_id"] for it in purchasable_items],
            category_ids=None,
        )
        if not valid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Code promo refuse: {reason}")
        applied_code = promo["code"]
        discount_value += promo_discount_value or 0.0
        total_after_discounts = discounted_total

    loyalty_points_used = 0
    loyalty_discount_value = 0.0
    requested_loyalty_points = int(getattr(order_in, "loyalty_points_to_use", 0) or 0)
    if requested_loyalty_points > 0:
        if not current_user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Connectez-vous pour utiliser vos points SR.")
        loyalty_settings = await loyalty_settings_out(db)
        loyalty_balance = await get_points_balance(db, user_id)
        loyalty_points_used, loyalty_discount_value = calculate_redeem(
            requested_loyalty_points,
            loyalty_balance,
            total_after_discounts,
            loyalty_settings,
        )
        total_after_discounts = max(0.0, round(total_after_discounts - loyalty_discount_value, 2))

    shipping_quote = await resolve_shipping_rate(
        db,
        country=order_in.shipping.country,
        city=order_in.shipping.city,
        order_total=total_after_discounts,
    )
    shipping_amount = shipping_quote["shipping_amount"]
    return {
        "subtotal": round(subtotal, 2),
        "pack_discount_value": pack_discount_value,
        "promo_code": applied_code,
        "promo_discount_value": promo_discount_value or 0.0,
        "discount_value": round(discount_value, 2),
        "loyalty_points_used": loyalty_points_used,
        "loyalty_discount_value": loyalty_discount_value,
        "shipping_amount": shipping_amount,
        "shipping_rate_id": shipping_quote["shipping_rate_id"],
        "shipping_rate_name": shipping_quote["shipping_rate_name"],
        "total_amount": round(total_after_discounts + shipping_amount, 2),
        "pack_items": pack_calculation["pack_items"],
    }


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def api_create_order(
    order_in: OrderCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db=Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    user_id = str(current_user["_id"]) if current_user else None
    customer_email = current_user["email"] if current_user else order_in.shipping.email

    # 1) Calcul des totaux côté serveur (hors livraison)
    subtotal = 0.0
    for it in order_in.items:
        subtotal += it.qty * it.unit_price
    pack_calculation = await calculate_order_packs(db, getattr(order_in, "pack_items", []))
    subtotal += pack_calculation["original_subtotal"]
    pack_discount_value = pack_calculation["discount_value"]
    purchasable_items = list(order_in.items) + pack_calculation["expanded_items"]

    total_amount = max(0.0, subtotal - pack_discount_value)
    discount_value = pack_discount_value
    applied_code = None
    promo_reserved = False
    loyalty_points_used = 0
    loyalty_discount_value = 0.0

    # 2) Si code promo, on valide ET on réserve l'usage de façon atomique
    if getattr(order_in, "promo_code", None):
        if not current_user:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Connectez-vous pour utiliser un code promo."
            )

        promo = await promo_crud.get_by_code(db, order_in.promo_code)
        if not promo:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code promo invalide")

        valid, reason, discounted_total, discount_val = validate_and_compute(
            promo,
            user_id=user_id,
            order_total=total_amount,
            product_ids=[it.product_id if hasattr(it, "product_id") else it["product_id"] for it in purchasable_items],
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
        discount_value += discount_val or 0.0
        total_amount = discounted_total
        promo_reserved = True

    # 2bis) Livraison (calculée côté backend depuis les tarifs CMS)
    after_discount = total_amount
    requested_loyalty_points = int(getattr(order_in, "loyalty_points_to_use", 0) or 0)
    if requested_loyalty_points > 0:
        if not current_user:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Connectez-vous pour utiliser vos points SR."
            )
        loyalty_settings = await loyalty_settings_out(db)
        loyalty_balance = await get_points_balance(db, user_id)
        loyalty_points_used, loyalty_discount_value = calculate_redeem(
            requested_loyalty_points,
            loyalty_balance,
            after_discount,
            loyalty_settings,
        )
        total_amount = max(0.0, round(after_discount - loyalty_discount_value, 2))

    after_loyalty = total_amount
    shipping_quote = await resolve_shipping_rate(
        db,
        country=order_in.shipping.country,
        city=order_in.shipping.city,
        order_total=after_loyalty,
    )
    shipping_amount = shipping_quote["shipping_amount"]
    total_amount = after_loyalty + shipping_amount

    # 3) Décrémenter le stock + créer la commande (avec rollback si erreur)
    decremented: List[Tuple[str, str, str, int]] = []
    new_order = None
    loyalty_redeemed = False
    try:
        for it in purchasable_items:
            product_id = it.product_id if hasattr(it, "product_id") else it["product_id"]
            color = it.color if hasattr(it, "color") else it["color"]
            size = it.size if hasattr(it, "size") else it["size"]
            qty = it.qty if hasattr(it, "qty") else it["qty"]
            await decrement_variant_stock(
                db,
                ObjectId(product_id),
                color,
                size,
                qty
            )
            decremented.append((product_id, color, size, qty))

        data = order_in.dict(exclude={"user_id"})
        data["user_id"] = user_id
        data["user_email"] = customer_email
        data["is_guest"] = current_user is None
        data["subtotal"] = subtotal
        data["discount_value"] = discount_value
        data["pack_discount_value"] = pack_discount_value
        data["pack_items"] = pack_calculation["pack_items"]
        data["promo_code"] = applied_code
        data["loyalty_points_used"] = loyalty_points_used
        data["loyalty_discount_value"] = loyalty_discount_value
        data["loyalty_eligible_amount"] = after_loyalty
        data["shipping_rate_id"] = shipping_quote["shipping_rate_id"]
        data["shipping_rate_name"] = shipping_quote["shipping_rate_name"]
        data["shipping_amount"] = shipping_amount
        data["total_amount"] = total_amount
        if promo_reserved:
            # flag interne pour savoir qu'on a déjà réservé (évite les doubles release)
            data["promo_reserved"] = True

        new_order = await crud_create_order(db, data)
        if applied_code:
            await track_event(
                db,
                "coupon_applied",
                user_id=user_id,
                order_id=new_order["id"],
                metadata={"coupon_code": applied_code, "discount_value": discount_value},
                request=request,
            )
        if data.get("payment_method") != "cod":
            await track_event(
                db,
                "payment_started",
                user_id=user_id,
                order_id=new_order["id"],
                metadata={"payment_method": data.get("payment_method"), "total_amount": total_amount},
                request=request,
            )
        await track_event(
            db,
            "order_completed",
            user_id=user_id,
            order_id=new_order["id"],
            metadata={
                "total_amount": total_amount,
                "payment_method": data.get("payment_method"),
                "items": [
                    {
                        "product_id": it["product_id"],
                        "color": it["color"],
                        "size": it["size"],
                        "qty": it["qty"],
                        "unit_price": it["unit_price"],
                    }
                    for it in new_order["items"]
                ],
            },
            request=request,
        )
        if loyalty_points_used > 0:
            await redeem_points_for_order(
                db,
                user_id=user_id,
                order_id=new_order["id"],
                points=loyalty_points_used,
                discount_value=loyalty_discount_value,
            )
            loyalty_redeemed = True

    except Exception:
        if loyalty_redeemed and new_order:
            try:
                await refund_redeemed_points(db, new_order, reason="Rollback commande")
            except Exception:
                pass
        if new_order:
            try:
                await db["orders"].delete_one({"_id": ObjectId(new_order["id"])})
            except Exception:
                pass
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
        "user_email": customer_email,
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
        "shipping_rate_name": new_order.get("shipping_rate_name"),
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
        recipient=customer_email,
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
    _admin=Depends(require_permission("orders")),
):
    oid = parse_oid(order_id)
    await update_order_status(db, oid, new_status)
    return {"message": "Statut mis à jour"}


@router.patch(
    "/{order_id}/pay",
    summary="Marquer la commande comme payée (COD) ou remboursée",
)
async def api_mark_paid(
    request: Request,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    _admin=Depends(require_permission("orders")),
):
    oid = parse_oid(order_id)
    await mark_paid(db, oid)
    earned_points = await award_points_for_paid_order(db, oid)
    await track_event(
        db,
        "payment_success",
        order_id=order_id,
        metadata={"loyalty_points_earned": earned_points},
        request=request,
    )
    # IMPORTANT: NE PLUS incrémenter ici — l'usage a déjà été "réservé" à la création
    return {"message": "Paiement enregistre", "loyalty_points_earned": earned_points}


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

    await refund_redeemed_points(db, ord_doc, reason="Annulation commande")

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
