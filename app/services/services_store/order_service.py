from datetime import datetime
from typing import List, Tuple

from bson import ObjectId
from fastapi import BackgroundTasks, HTTPException, Request, status
from jinja2 import Environment, FileSystemLoader

from app.analytics.service import track_event
from app.config import settings
from app.crud import order as order_crud
from app.crud import product as product_crud
from app.crud import promocodes as promo_crud
from app.crud.shipping_rate import resolve_shipping_rate
from app.crud.variant import decrement_variant_stock, increment_variant_stock
from app.schemas.order import OrderCreate
from app.services.services_erp.notification_service import create_notification
from app.services.services_store.discounts import validate_and_compute
from app.services.services_store.email import send_email
from app.services.services_store.loyalty_service import (
    calculate_redeem,
    get_points_balance,
    loyalty_settings_out,
    redeem_points_for_order,
    refund_redeemed_points,
)
from app.services.services_store.pack_service import calculate_order_packs


jinja_env = Environment(loader=FileSystemLoader("templates"), autoescape=True)


def parse_oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID de commande invalide")


def _item_value(item, key: str):
    return getattr(item, key) if hasattr(item, key) else item[key]


async def quote_order(db, order_in: OrderCreate, request: Request, current_user):
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
            product_ids=[_item_value(it, "product_id") for it in purchasable_items],
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


async def product_display_name(db, product_id: str) -> str:
    product = await product_crud.find_product_name(db, ObjectId(product_id))
    return (product or {}).get("full_name") or (product or {}).get("name") or product_id


async def build_order_email_data(db, order_doc: dict, customer_email: str) -> dict:
    return {
        "id": order_doc["id"],
        "date": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
        "user_email": customer_email,
        "items": [
            {
                "product_id": it["product_id"],
                "name": await product_display_name(db, it["product_id"]),
                "color": it["color"],
                "size": it["size"],
                "qty": it["qty"],
                "unit_price": it["unit_price"],
            }
            for it in order_doc["items"]
        ],
        "total_amount": order_doc["total_amount"],
        "shipping": order_doc["shipping"],
        "shipping_amount": order_doc.get("shipping_amount", 0),
        "shipping_rate_name": order_doc.get("shipping_rate_name"),
        "subtotal": order_doc.get("subtotal"),
        "discount_value": order_doc.get("discount_value"),
        "promo_code": order_doc.get("promo_code"),
    }


def _confirmation_text(order_data: dict) -> str:
    text_lines = [
        f"Commande #{order_data['id']} - {order_data['date']}",
        "Articles :",
        *[
            f" - {it['qty']}x {it['name']} ({it['color']}/{it['size']}): {it['qty'] * it['unit_price']:.2f}TND"
            for it in order_data["items"]
        ],
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
    return "\n".join(text_lines)


def _admin_new_order_text(order_data: dict) -> str:
    return "\n".join([
        f"Nouvelle commande #{order_data['id']} par {order_data['user_email']}",
        "",
        *[
            f"- {it['qty']}x {it['name']} ({it['color']}/{it['size']}): {it['qty'] * it['unit_price']:.2f}TND"
            for it in order_data["items"]
        ],
        "",
        *([f"Sous-total : {order_data['subtotal']:.2f} TND"] if order_data.get("subtotal") is not None else []),
        *([f"Remise ({order_data['promo_code']}) : -{order_data['discount_value']:.2f} TND"]
          if order_data.get("discount_value") else []),
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


def enqueue_order_created_emails(background_tasks: BackgroundTasks, order_data: dict, customer_email: str) -> None:
    tpl_client = jinja_env.get_template("order_confirmation.html")
    html_client = tpl_client.render(
        order=order_data,
        logo_url=settings.LOGO_URL,
        support_email=settings.ADMIN_EMAIL,
    )
    background_tasks.add_task(
        send_email,
        subject=f"Votre commande #{order_data['id']} - Savage Rise",
        recipient=customer_email,
        body=_confirmation_text(order_data),
        html=html_client,
    )

    tpl_admin = jinja_env.get_template("order_notification_admin.html")
    html_admin = tpl_admin.render(
        order=order_data,
        logo_url=settings.LOGO_URL,
        admin_panel_url=settings.FRONTEND_URL,
    )
    background_tasks.add_task(
        send_email,
        subject=f"Nouvelle commande #{order_data['id']}",
        recipient=settings.ADMIN_EMAIL,
        body=_admin_new_order_text(order_data),
        html=html_admin,
    )


async def create_order(db, order_in: OrderCreate, background_tasks: BackgroundTasks, request: Request, current_user):
    user_id = str(current_user["_id"]) if current_user else None
    customer_email = current_user["email"] if current_user else order_in.shipping.email

    subtotal = sum(it.qty * it.unit_price for it in order_in.items)
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

    if getattr(order_in, "promo_code", None):
        if not current_user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Connectez-vous pour utiliser un code promo.")
        promo = await promo_crud.get_by_code(db, order_in.promo_code)
        if not promo:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code promo invalide")
        valid, reason, discounted_total, discount_val = validate_and_compute(
            promo,
            user_id=user_id,
            order_total=total_amount,
            product_ids=[_item_value(it, "product_id") for it in purchasable_items],
            category_ids=None,
        )
        if not valid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Code promo refuse: {reason}")
        reserved = await promo_crud.reserve_use(db, promo["code"], user_id)
        if not reserved:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ce code promo n'est plus disponible ou a deja ete utilise par ce compte.")
        applied_code = promo["code"]
        discount_value += discount_val or 0.0
        total_amount = discounted_total
        promo_reserved = True

    requested_loyalty_points = int(getattr(order_in, "loyalty_points_to_use", 0) or 0)
    if requested_loyalty_points > 0:
        if not current_user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Connectez-vous pour utiliser vos points SR.")
        loyalty_settings = await loyalty_settings_out(db)
        loyalty_balance = await get_points_balance(db, user_id)
        loyalty_points_used, loyalty_discount_value = calculate_redeem(
            requested_loyalty_points,
            loyalty_balance,
            total_amount,
            loyalty_settings,
        )
        total_amount = max(0.0, round(total_amount - loyalty_discount_value, 2))

    after_loyalty = total_amount
    shipping_quote = await resolve_shipping_rate(
        db,
        country=order_in.shipping.country,
        city=order_in.shipping.city,
        order_total=after_loyalty,
    )
    shipping_amount = shipping_quote["shipping_amount"]
    total_amount = after_loyalty + shipping_amount

    decremented: List[Tuple[str, str, str, int]] = []
    new_order = None
    loyalty_redeemed = False
    try:
        for it in purchasable_items:
            product_id = _item_value(it, "product_id")
            color = _item_value(it, "color")
            size = _item_value(it, "size")
            qty = _item_value(it, "qty")
            await decrement_variant_stock(db, ObjectId(product_id), color, size, qty)
            decremented.append((product_id, color, size, qty))

        data = order_in.dict(exclude={"user_id"})
        data.update({
            "user_id": user_id,
            "user_email": customer_email,
            "is_guest": current_user is None,
            "subtotal": subtotal,
            "discount_value": discount_value,
            "pack_discount_value": pack_discount_value,
            "pack_items": pack_calculation["pack_items"],
            "promo_code": applied_code,
            "loyalty_points_used": loyalty_points_used,
            "loyalty_discount_value": loyalty_discount_value,
            "loyalty_eligible_amount": after_loyalty,
            "shipping_rate_id": shipping_quote["shipping_rate_id"],
            "shipping_rate_name": shipping_quote["shipping_rate_name"],
            "shipping_amount": shipping_amount,
            "total_amount": total_amount,
        })
        if promo_reserved:
            data["promo_reserved"] = True

        new_order = await order_crud.create_order(db, data)

        if applied_code:
            await track_event(db, "coupon_applied", user_id=user_id, order_id=new_order["id"], metadata={"coupon_code": applied_code, "discount_value": discount_value}, request=request)
        if data.get("payment_method") != "cod":
            await track_event(db, "payment_started", user_id=user_id, order_id=new_order["id"], metadata={"payment_method": data.get("payment_method"), "total_amount": total_amount}, request=request)
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
            await redeem_points_for_order(db, user_id=user_id, order_id=new_order["id"], points=loyalty_points_used, discount_value=loyalty_discount_value)
            loyalty_redeemed = True

        try:
            await create_notification(
                db,
                {
                    "audience": "erp",
                    "category": "orders",
                    "title": "Nouvelle commande",
                    "message": f"Commande #{new_order['id']} creee pour {total_amount:.2f} TND",
                    "priority": "high",
                    "source_module": "orders",
                    "action_url": f"/admin/orders/{new_order['id']}",
                    "metadata": {
                        "order_id": new_order["id"],
                        "user_email": customer_email,
                        "total_amount": total_amount,
                        "payment_method": data.get("payment_method"),
                    },
                },
            )
        except Exception:
            pass
    except Exception:
        if loyalty_redeemed and new_order:
            try:
                await refund_redeemed_points(db, new_order, reason="Rollback commande")
            except Exception:
                pass
        if new_order:
            try:
                await order_crud.delete_order_by_id(db, ObjectId(new_order["id"]))
            except Exception:
                pass
        for pid, color, size, qty in reversed(decremented):
            try:
                await increment_variant_stock(db, ObjectId(pid), color, size, qty)
            except Exception:
                pass
        if promo_reserved and applied_code:
            try:
                await promo_crud.release_use(db, applied_code, user_id)
            except Exception:
                pass
        raise

    order_data = await build_order_email_data(db, new_order, customer_email)
    enqueue_order_created_emails(background_tasks, order_data, customer_email)
    return new_order


def _cancellation_text(order_data: dict) -> str:
    text_lines = [
        f"Annulation de votre commande #{order_data['id']} - {order_data['date']}",
        "",
        "Details des articles annules :",
        *[
            f"- {it['qty']}x {it['name']} ({it['color']}/{it['size']}): {it['qty'] * it['unit_price']:.2f}TND"
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
    return "\n".join(text_lines)


def enqueue_order_cancelled_emails(background_tasks: BackgroundTasks, order_data: dict, customer_email: str) -> None:
    tpl_client = jinja_env.get_template("order_cancellation_client.html")
    html_client = tpl_client.render(order=order_data, logo_url=settings.LOGO_URL, support_email=settings.ADMIN_EMAIL)
    background_tasks.add_task(
        send_email,
        subject=f"Commande #{order_data['id']} annulee - Savage Rise",
        recipient=customer_email,
        body=_cancellation_text(order_data),
        html=html_client,
    )

    tpl_admin = jinja_env.get_template("order_cancellation_admin.html")
    html_admin = tpl_admin.render(order=order_data, logo_url=settings.LOGO_URL, admin_panel_url=settings.FRONTEND_URL)
    background_tasks.add_task(
        send_email,
        subject=f"Commande annulee #{order_data['id']}",
        recipient=settings.ADMIN_EMAIL,
        body="\n".join([f"Commande annulee #{order_data['id']} par {order_data['user_email']}", "", _cancellation_text(order_data)]),
        html=html_admin,
    )


async def cancel_order(db, order_id: str, background_tasks: BackgroundTasks, current_user):
    oid = parse_oid(order_id)
    ord_doc = await order_crud.get_order(db, oid)
    if not ord_doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    if ord_doc["user_id"] != str(current_user["_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez annuler que vos propres commandes")
    if ord_doc["status"] != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Commande non annulable (statut != pending)")

    for it in ord_doc["items"]:
        await increment_variant_stock(db, ObjectId(it["product_id"]), it["color"], it["size"], it["qty"])

    if ord_doc.get("promo_code"):
        try:
            await promo_crud.release_use(db, ord_doc["promo_code"], ord_doc.get("user_id"))
        except Exception:
            pass

    await refund_redeemed_points(db, ord_doc, reason="Annulation commande")
    await order_crud.update_order_status(db, oid, "cancelled")
    updated = await order_crud.get_order(db, oid)

    order_data = await build_order_email_data(db, updated, current_user["email"])
    enqueue_order_cancelled_emails(background_tasks, order_data, current_user["email"])

    await track_event(
        db,
        "order_cancelled",
        user_id=str(current_user["_id"]),
        order_id=order_id,
        metadata={
            "total_amount": updated.get("total_amount"),
            "items_count": len(updated.get("items", [])),
            "promo_code": updated.get("promo_code"),
        },
        request=None,
    )
    return updated
