import hashlib
import json
from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.analytics.service import track_event
from app.config import settings
from app.crud import order as order_crud
from app.crud import pack as pack_crud
from app.crud import product as product_crud
from app.crud import promocodes as promo_crud
from app.crud.shipping_rate import resolve_shipping_rate
from app.domain.inventory import inventory_projection, stock_available_value
from app.domain.order_constants import (
    FULFILLMENT_STATUS_CANCELLED,
    FULFILLMENT_STATUS_FULFILLED,
    FULFILLMENT_STATUS_PROCESSING,
    FULFILLMENT_STATUS_RESERVED,
    FULFILLMENT_STATUS_RETURNED,
    FULFILLMENT_STATUS_RETURNING,
    INVENTORY_MOVEMENT_RELEASE,
    INVENTORY_MOVEMENT_RESERVATION,
    INVENTORY_MOVEMENT_RETURN_DAMAGED,
    INVENTORY_MOVEMENT_RETURN_RESTOCKED,
    INVENTORY_MOVEMENT_SALE,
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_CONFIRMED,
    ORDER_STATUS_DELIVERED,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_RETURNED,
    ORDER_STATUS_RETURN_IN_TRANSIT,
    ORDER_STATUS_RETURN_RECEIVED,
    ORDER_STATUS_RETURN_REQUESTED,
    ORDER_STATUS_SHIPPED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PARTIALLY_REFUNDED,
    PAYMENT_STATUS_REFUNDED,
    PAYMENT_STATUS_UNPAID,
)
from app.domain.order_errors import (
    InsufficientStockError,
    InvalidIdempotencyKeyReuseError,
    InvalidOrderTransitionError,
    OrderAlreadyCancelledError,
    OrderAlreadyPaidError,
)
from app.domain.order_state_machine import ensure_order_transition, fulfillment_status_for_order_status, payment_status_after_refund
from app.integrations.meta import build_meta_context, enqueue_purchase_event, process_meta_outbox_operation
from app.integrations.meta.service import persisted_meta_context
from app.services.services_store import outbox_service
from app.services.services_store.loyalty_service import (
    add_loyalty_transaction,
    award_points_for_paid_order,
    calculate_redeem,
    get_points_balance,
    loyalty_settings_out,
    redeem_points_for_order,
    refund_redeemed_points,
)
from app.services.services_store.meta_ids import meta_variant_content_id
from app.services.services_store.order_history_service import append_history


def _parse_oid(value: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} invalide")


def _actor_ref(actor_type: str, actor_id: Optional[str]) -> Optional[str]:
    if not actor_id:
        return actor_type
    return f"{actor_type}:{actor_id}"


def _payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _round_money(value: float) -> float:
    return round(float(value), 2)


def _stock_insufficient_detail(*, product_id: str, color: str, size: str, requested_qty: int, available_qty: int) -> str:
    return (
        f"Stock insuffisant pour {color}/{size}. "
        f"Demande={requested_qty}, disponible={available_qty}, produit={product_id}"
    )


def _distribute_discount(lines: list[dict[str, Any]], discount_total: float) -> None:
    discount_total = _round_money(discount_total)
    if discount_total <= 0 or not lines:
        for line in lines:
            line["discount_amount"] = 0.0
            line["unit_price"] = line["unit_price_original"]
            line["unit_price_final"] = line["unit_price_original"]
            line["line_total"] = _round_money(line["unit_price_original"] * line["qty"])
        return

    total_original = sum(_round_money(line["unit_price_original"] * line["qty"]) for line in lines)
    allocated = 0.0
    for index, line in enumerate(lines):
        original_total = _round_money(line["unit_price_original"] * line["qty"])
        if index == len(lines) - 1:
            line_discount = _round_money(discount_total - allocated)
        else:
            ratio = (original_total / total_original) if total_original > 0 else 0
            line_discount = _round_money(discount_total * ratio)
            allocated = _round_money(allocated + line_discount)
        final_total = _round_money(max(0.0, original_total - line_discount))
        qty = max(int(line["qty"]), 1)
        line["discount_amount"] = line_discount
        line["unit_price_final"] = _round_money(final_total / qty)
        line["unit_price"] = line["unit_price_final"]
        line["line_total"] = final_total


def _order_doc_to_out(doc: dict) -> dict:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    payload["status"] = payload.get("order_status", payload.get("status"))
    payload["order_status"] = payload["status"]
    payload.setdefault("fulfillment_status", FULFILLMENT_STATUS_RESERVED)
    payload.setdefault("payment_status", PAYMENT_STATUS_UNPAID)
    payload.setdefault("item_snapshots", [])
    payload.setdefault("inventory_allocations", [])
    payload.setdefault("pack_items", [])
    payload.setdefault("refunded_amount", 0)
    return payload


async def _find_product_snapshot(db, product_id: str) -> dict:
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
    return product


def _find_variant_or_fail(product: dict, color: str, size: str) -> dict:
    for variant in product.get("variants", []):
        if variant.get("color") != color:
            continue
        for row in variant.get("sizes", []):
            if row.get("size") == size:
                projected = inventory_projection(dict(row))
                if projected["stock_available"] < 0:
                    raise HTTPException(status.HTTP_409_CONFLICT, "Stock incoherent")
                return projected
    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Variante {color}/{size} introuvable")


async def _build_order_materialization(db, order_in) -> dict:
    base_items = []
    item_snapshots = []
    inventory_allocations: dict[tuple[str, str, str], dict[str, Any]] = {}
    subtotal = 0.0

    for item in order_in.items:
        product = await _find_product_snapshot(db, item.product_id)
        variant_row = _find_variant_or_fail(product, item.color, item.size)
        unit_price = float(product["price"])
        qty = int(item.qty)
        if int(variant_row["stock_available"]) < qty:
            raise InsufficientStockError(
                _stock_insufficient_detail(
                    product_id=item.product_id,
                    color=item.color,
                    size=item.size,
                    requested_qty=qty,
                    available_qty=int(variant_row["stock_available"]),
                )
            )
        line_total = _round_money(unit_price * qty)
        subtotal += line_total
        snapshot = {
            "item_type": "single",
            "product_id": item.product_id,
            "variant_id": f"{item.product_id}:{item.color}:{item.size}",
            "sku": product.get("sku"),
            "meta_content_id": meta_variant_content_id(item.product_id, color=item.color, size=item.size),
            "product_name": product.get("full_name") or product.get("name"),
            "color": item.color,
            "size": item.size,
            "unit_price_original": unit_price,
            "unit_price": unit_price,
            "unit_price_final": unit_price,
            "discount_amount": 0.0,
            "qty": qty,
            "line_total": line_total,
            "pack_id": None,
            "pack_title": None,
            "stock_available": int(variant_row["stock_available"]),
        }
        item_snapshots.append(snapshot)
        base_items.append({"product_id": item.product_id, "color": item.color, "size": item.size, "qty": qty})
        key = (item.product_id, item.color, item.size)
        inventory_allocations.setdefault(key, {"product_id": item.product_id, "color": item.color, "size": item.size, "qty": 0})
        inventory_allocations[key]["qty"] += qty

    pack_items_out = []
    pack_discount_total = 0.0
    for selection in order_in.pack_items or []:
        pack = await pack_crud.find_pack_by_id(db, _parse_oid(selection.pack_id, "Pack ID"))
        if not pack or pack.get("status") != "active":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pack indisponible")
        components = pack.get("components") or [{"id": str(index), "product_id": pid, "qty": 1} for index, pid in enumerate(pack.get("product_ids", []), start=1)]
        components_by_id = {component["id"]: component for component in components}
        pack_original = 0.0
        component_payloads = []
        pack_component_snapshots = []
        for item in selection.items:
            component = components_by_id.get(item.component_id) if item.component_id else None
            if component is None:
                matches = [candidate for candidate in components if candidate["product_id"] == item.product_id]
                if len(matches) != 1:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "component_id requis pour ce pack")
                component = matches[0]
            product = await _find_product_snapshot(db, item.product_id)
            if component["product_id"] != item.product_id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Produit invalide pour le pack")
            if component.get("color") and component["color"] != item.color:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Couleur invalide pour le pack")
            if component.get("size") and component["size"] != item.size:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Taille invalide pour le pack")
            variant_row = _find_variant_or_fail(product, item.color, item.size)
            unit_price = float(product["price"])
            line_qty = int(selection.qty) * int(component.get("qty", 1) or 1) * int(item.qty)
            if int(variant_row["stock_available"]) < line_qty:
                raise InsufficientStockError(
                    _stock_insufficient_detail(
                        product_id=item.product_id,
                        color=item.color,
                        size=item.size,
                        requested_qty=line_qty,
                        available_qty=int(variant_row["stock_available"]),
                    )
                )
            line_total = _round_money(unit_price * line_qty)
            pack_original += line_total
            key = (item.product_id, item.color, item.size)
            inventory_allocations.setdefault(key, {"product_id": item.product_id, "color": item.color, "size": item.size, "qty": 0})
            inventory_allocations[key]["qty"] += line_qty
            pack_component_snapshots.append({
                "item_type": "pack_component",
                "product_id": item.product_id,
                "variant_id": f"{item.product_id}:{item.color}:{item.size}",
                "sku": product.get("sku"),
                "meta_content_id": meta_variant_content_id(item.product_id, color=item.color, size=item.size),
                "product_name": product.get("full_name") or product.get("name"),
                "color": item.color,
                "size": item.size,
                "unit_price_original": unit_price,
                "unit_price": unit_price,
                "unit_price_final": unit_price,
                "discount_amount": 0.0,
                "qty": line_qty,
                "line_total": line_total,
                "pack_id": str(pack["_id"]),
                "pack_title": pack.get("title"),
                "pack_component_id": component["id"],
                "stock_available": int(variant_row["stock_available"]),
            })
            component_payloads.append({
                "component_id": component["id"],
                "product_id": item.product_id,
                "color": item.color,
                "size": item.size,
                "qty": int(component.get("qty", 1) or 1) * int(item.qty),
                "unit_price_original": unit_price,
            })

        if pack.get("discount_type") == "percent":
            pack_discount = pack_original * (float(pack.get("discount_value", 0)) / 100)
        else:
            pack_discount = float(pack.get("discount_value", 0)) * int(selection.qty)
        pack_discount = _round_money(min(max(pack_discount, 0), pack_original))
        _distribute_discount(pack_component_snapshots, pack_discount)
        item_snapshots.extend(pack_component_snapshots)
        pack_discount_total += pack_discount
        subtotal += pack_original
        pack_items_out.append({
            "pack_id": str(pack["_id"]),
            "title": pack["title"],
            "qty": int(selection.qty),
            "items": component_payloads,
            "original_amount": _round_money(pack_original),
            "discount_amount": pack_discount,
            "final_amount": _round_money(pack_original - pack_discount),
        })

    return {
        "base_items": base_items,
        "item_snapshots": item_snapshots,
        "inventory_allocations": list(inventory_allocations.values()),
        "pack_items": pack_items_out,
        "subtotal": _round_money(subtotal),
        "pack_discount_value": _round_money(pack_discount_total),
    }


async def quote_order(db, order_in, current_user):
    materialized = await _build_order_materialization(db, order_in)
    user_id = str(current_user["_id"]) if current_user else None
    order_total_before_promos = max(0.0, materialized["subtotal"] - materialized["pack_discount_value"])
    discount_value = materialized["pack_discount_value"]
    applied_code = None
    promo_discount_value = 0.0
    if order_in.promo_code:
        if not current_user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Connectez-vous pour utiliser un code promo.")
        promo = await promo_crud.get_by_code(db, order_in.promo_code)
        if not promo:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code promo invalide")
        from app.services.services_store.discounts import validate_and_compute

        valid, reason, discounted_total, promo_discount_value = validate_and_compute(
            promo,
            user_id=user_id,
            order_total=order_total_before_promos,
            product_ids=[row["product_id"] for row in materialized["inventory_allocations"]],
            category_ids=None,
        )
        if not valid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Code promo refuse: {reason}")
        applied_code = promo["code"]
        discount_value += promo_discount_value or 0.0
        order_total_before_promos = discounted_total
    loyalty_points_used = 0
    loyalty_discount_value = 0.0
    if order_in.loyalty_points_to_use > 0:
        if not current_user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Connectez-vous pour utiliser vos points SR.")
        settings_data = await loyalty_settings_out(db)
        loyalty_balance = await get_points_balance(db, user_id)
        loyalty_points_used, loyalty_discount_value = calculate_redeem(
            order_in.loyalty_points_to_use,
            loyalty_balance,
            order_total_before_promos,
            settings_data,
        )
        order_total_before_promos = max(0.0, _round_money(order_total_before_promos - loyalty_discount_value))
    shipping_quote = await resolve_shipping_rate(
        db,
        country=order_in.shipping.country,
        city=order_in.shipping.city,
        order_total=order_total_before_promos,
    )
    total_amount = _round_money(order_total_before_promos + shipping_quote["shipping_amount"])
    promotion = None
    if applied_code:
        promotion = {"code": applied_code, "discount_amount": _round_money(promo_discount_value or 0.0)}
    loyalty = None
    if order_in.loyalty_points_to_use > 0 or loyalty_points_used > 0:
        loyalty = {
            "points_requested": int(order_in.loyalty_points_to_use),
            "points_used": int(loyalty_points_used),
            "discount_amount": _round_money(loyalty_discount_value),
        }
    return {
        "currency": settings.META_CATALOG_CURRENCY,
        "subtotal": materialized["subtotal"],
        "pack_discount": materialized["pack_discount_value"],
        "promotion_discount": _round_money(promo_discount_value or 0.0),
        "loyalty_discount": _round_money(loyalty_discount_value),
        "shipping_amount": shipping_quote["shipping_amount"],
        "total": total_amount,
        "items": materialized["item_snapshots"],
        "promotion": promotion,
        "loyalty": loyalty,
        "warnings": [],
        "pack_discount_value": materialized["pack_discount_value"],
        "promo_code": applied_code,
        "promo_discount_value": _round_money(promo_discount_value or 0.0),
        "discount_value": _round_money(discount_value),
        "loyalty_points_used": loyalty_points_used,
        "loyalty_discount_value": _round_money(loyalty_discount_value),
        "shipping_amount": shipping_quote["shipping_amount"],
        "shipping_rate_id": shipping_quote["shipping_rate_id"],
        "shipping_rate_name": shipping_quote["shipping_rate_name"],
        "total_amount": total_amount,
        "pack_items": materialized["pack_items"],
        "item_snapshots": materialized["item_snapshots"],
        "inventory_allocations": materialized["inventory_allocations"],
    }


async def _insert_inventory_movement(session, db, *, movement_type: str, allocation: dict, order_id: str, order_item_key: str, on_hand_delta: int, reserved_delta: int, reason: str, source: str):
    doc = {
        "variant_id": f"{allocation['product_id']}:{allocation['color']}:{allocation['size']}",
        "product_id": allocation["product_id"],
        "order_id": order_id,
        "order_item_id": order_item_key,
        "movement_type": movement_type,
        "on_hand_delta": on_hand_delta,
        "reserved_delta": reserved_delta,
        "reason": reason,
        "source": source,
        "operation_key": f"order:{order_id}:item:{order_item_key}:{movement_type}",
        "metadata": {
            "color": allocation["color"],
            "size": allocation["size"],
            "qty": allocation["qty"],
        },
        "created_at": datetime.utcnow(),
    }
    try:
        await db["inventory_movements"].insert_one(doc, session=session)
    except DuplicateKeyError:
        return


async def _load_variant_size(session, db, allocation: dict) -> dict:
    product = await db["products"].find_one(
        {"_id": _parse_oid(allocation["product_id"], "Produit ID")},
        {"variants": 1},
        session=session,
    )
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
    for variant in product.get("variants", []):
        if variant.get("color") != allocation["color"]:
            continue
        for row in variant.get("sizes", []):
            if row.get("size") == allocation["size"]:
                return inventory_projection(dict(row))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Variante introuvable")


async def _reserve_allocation(session, db, allocation: dict, order_id: str, order_item_key: str):
    qty = int(allocation["qty"])
    current = await _load_variant_size(session, db, allocation)
    if current["stock_available"] < qty:
        raise InsufficientStockError(
            _stock_insufficient_detail(
                product_id=allocation["product_id"],
                color=allocation["color"],
                size=allocation["size"],
                requested_qty=qty,
                available_qty=int(current["stock_available"]),
            )
        )
    result = await db["products"].update_one(
        {
            "_id": _parse_oid(allocation["product_id"], "Produit ID"),
            "variants.color": allocation["color"],
        },
        {"$inc": {"variants.$.sizes.$[s].stock_reserved": qty}},
        array_filters=[{"s.size": allocation["size"], "s.stock_on_hand": current["stock_on_hand"], "s.stock_reserved": current["stock_reserved"]}],
        session=session,
    )
    if result.modified_count == 0:
        raise InsufficientStockError(
            _stock_insufficient_detail(
                product_id=allocation["product_id"],
                color=allocation["color"],
                size=allocation["size"],
                requested_qty=qty,
                available_qty=int(current["stock_available"]),
            )
        )
    await _insert_inventory_movement(
        session,
        db,
        movement_type=INVENTORY_MOVEMENT_RESERVATION,
        allocation=allocation,
        order_id=order_id,
        order_item_key=order_item_key,
        on_hand_delta=0,
        reserved_delta=qty,
        reason="order_created",
        source="order_workflow",
    )


async def _release_allocation(session, db, allocation: dict, order_id: str, order_item_key: str, reason: str):
    qty = int(allocation["qty"])
    current = await _load_variant_size(session, db, allocation)
    if current["stock_reserved"] < qty:
        raise InvalidOrderTransitionError("Impossible de liberer la reservation de stock")
    result = await db["products"].update_one(
        {"_id": _parse_oid(allocation["product_id"], "Produit ID"), "variants.color": allocation["color"]},
        {"$inc": {"variants.$.sizes.$[s].stock_reserved": -qty}},
        array_filters=[{"s.size": allocation["size"], "s.stock_on_hand": current["stock_on_hand"], "s.stock_reserved": current["stock_reserved"]}],
        session=session,
    )
    if result.modified_count == 0:
        raise InvalidOrderTransitionError("Impossible de liberer la reservation de stock")
    await _insert_inventory_movement(
        session,
        db,
        movement_type=INVENTORY_MOVEMENT_RELEASE,
        allocation=allocation,
        order_id=order_id,
        order_item_key=order_item_key,
        on_hand_delta=0,
        reserved_delta=-qty,
        reason=reason,
        source="order_workflow",
    )


async def _fulfill_allocation(session, db, allocation: dict, order_id: str, order_item_key: str):
    qty = int(allocation["qty"])
    current = await _load_variant_size(session, db, allocation)
    if current["stock_reserved"] < qty or current["stock_on_hand"] < qty:
        raise InvalidOrderTransitionError("Impossible de consommer la reservation de stock")
    result = await db["products"].update_one(
        {"_id": _parse_oid(allocation["product_id"], "Produit ID"), "variants.color": allocation["color"]},
        {"$inc": {"variants.$.sizes.$[s].stock_on_hand": -qty, "variants.$.sizes.$[s].stock_reserved": -qty}},
        array_filters=[{"s.size": allocation["size"], "s.stock_on_hand": current["stock_on_hand"], "s.stock_reserved": current["stock_reserved"]}],
        session=session,
    )
    if result.modified_count == 0:
        raise InvalidOrderTransitionError("Impossible de consommer la reservation de stock")
    await _insert_inventory_movement(
        session,
        db,
        movement_type=INVENTORY_MOVEMENT_SALE,
        allocation=allocation,
        order_id=order_id,
        order_item_key=order_item_key,
        on_hand_delta=-qty,
        reserved_delta=-qty,
        reason="order_shipped",
        source="order_workflow",
    )


async def _acquire_order_idempotency(db, idempotency_key: str, payload_hash: str) -> dict:
    now = datetime.utcnow()
    marker = {
        "key": idempotency_key,
        "payload_hash": payload_hash,
        "status": "in_progress",
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db["order_idempotency"].insert_one(marker)
        return marker
    except DuplicateKeyError:
        existing = await db["order_idempotency"].find_one({"key": idempotency_key})
        if existing and existing.get("payload_hash") != payload_hash:
            raise InvalidIdempotencyKeyReuseError()
        if existing and existing.get("status") == "completed" and existing.get("order_id"):
            order = await db["orders"].find_one({"_id": _parse_oid(existing["order_id"], "Commande ID")})
            if order:
                return {"order": order}
        raise HTTPException(status.HTTP_409_CONFLICT, "Une requete avec cette cle d'idempotence est deja en cours")


async def _complete_order_idempotency(db, idempotency_key: str, order_id: str) -> None:
    await db["order_idempotency"].update_one(
        {"key": idempotency_key},
        {"$set": {"status": "completed", "order_id": order_id, "updated_at": datetime.utcnow()}},
    )


async def create_order(db, order_in, background_tasks, request, current_user, *, idempotency_key: str):
    if not idempotency_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Idempotency-Key requis")
    payload_hash = _payload_hash(order_in.model_dump(mode="json"))
    marker = await _acquire_order_idempotency(db, idempotency_key, payload_hash)
    if marker.get("order"):
        return _order_doc_to_out(marker["order"])
    existing = await db["orders"].find_one({"idempotency_key": idempotency_key})
    if existing:
        if existing.get("payload_hash") != payload_hash:
            raise InvalidIdempotencyKeyReuseError()
        await _complete_order_idempotency(db, idempotency_key, str(existing["_id"]))
        return _order_doc_to_out(existing)
    try:
        quote = await quote_order(db, order_in, current_user)
        user_id = str(current_user["_id"]) if current_user else None
        customer_email = current_user["email"] if current_user else order_in.shipping.email
        now = datetime.utcnow()
        meta_context = build_meta_context(request, order_in.meta)
        meta_enqueued = False
        order_doc = {
            "user_id": user_id,
            "user_email": customer_email,
            "is_guest": current_user is None,
            "shipping": order_in.shipping.model_dump(),
            "meta_context": persisted_meta_context(meta_context),
            "items": [item.model_dump() for item in order_in.items],
            "pack_items": quote["pack_items"],
            "item_snapshots": quote["item_snapshots"],
            "inventory_allocations": quote["inventory_allocations"],
            "payment_method": order_in.payment_method,
            "payment_status": PAYMENT_STATUS_UNPAID,
            "status": ORDER_STATUS_PENDING,
            "order_status": ORDER_STATUS_PENDING,
            "fulfillment_status": FULFILLMENT_STATUS_RESERVED,
            "subtotal": quote["subtotal"],
            "discount_value": quote["discount_value"],
            "pack_discount_value": quote["pack_discount_value"],
            "promo_code": quote.get("promo_code"),
            "loyalty_points_to_use": order_in.loyalty_points_to_use,
            "loyalty_points_used": quote["loyalty_points_used"],
            "loyalty_discount_value": quote["loyalty_discount_value"],
            "loyalty_eligible_amount": max(0.0, quote["total_amount"] - quote["shipping_amount"]),
            "loyalty_points_earned": 0,
            "loyalty_points_awarded": False,
            "loyalty_points_refunded": False,
            "shipping_amount": quote["shipping_amount"],
            "shipping_rate_id": quote["shipping_rate_id"],
            "shipping_rate_name": quote["shipping_rate_name"],
            "total_amount": quote["total_amount"],
            "refunded_amount": 0.0,
            "idempotency_key": idempotency_key,
            "payload_hash": payload_hash,
            "created_at": now,
            "updated_at": now,
        }
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                if order_doc["promo_code"]:
                    reserved = await promo_crud.reserve_use(db, order_doc["promo_code"], user_id, session=session)
                    if not reserved:
                        raise HTTPException(status.HTTP_409_CONFLICT, "Ce code promo n'est plus disponible ou a deja ete utilise par ce compte.")
                insert_result = await db["orders"].insert_one(order_doc, session=session)
                order_id = str(insert_result.inserted_id)
                for index, allocation in enumerate(order_doc["inventory_allocations"]):
                    await _reserve_allocation(session, db, allocation, order_id, str(index))
                if quote["loyalty_points_used"] > 0:
                    await redeem_points_for_order(
                        db,
                        user_id=user_id,
                        order_id=order_id,
                        points=quote["loyalty_points_used"],
                        discount_value=quote["loyalty_discount_value"],
                        session=session,
                    )
                await append_history(
                    db,
                    session=session,
                    order_id=order_id,
                    event_type="order_created",
                    to_order_status=ORDER_STATUS_PENDING,
                    to_payment_status=PAYMENT_STATUS_UNPAID,
                    to_fulfillment_status=FULFILLMENT_STATUS_RESERVED,
                    changed_by=user_id,
                    actor_type="customer" if user_id else "guest",
                    metadata={"idempotency_key": idempotency_key},
                )
                await outbox_service.enqueue(
                    db,
                    session=session,
                    event_type="order_created",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    operation_key=f"order:{order_id}:created",
                    payload={"order_id": order_id},
                )
                if customer_email:
                    await outbox_service.enqueue(
                        db,
                        session=session,
                        event_type="send_order_email",
                        aggregate_type="order",
                        aggregate_id=order_id,
                        operation_key=f"order:{order_id}:send-email",
                        payload={"order_id": order_id, "recipient": customer_email},
                    )
                await outbox_service.enqueue(
                    db,
                    session=session,
                    event_type="analytics_order_completed",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    operation_key=f"order:{order_id}:analytics-order-completed",
                    payload={"order_id": order_id},
                )
                meta_enqueued = await enqueue_purchase_event(
                    db,
                    {"_id": insert_result.inserted_id, **order_doc},
                    session=session,
                    meta_context=meta_context,
                )
        created = await db["orders"].find_one({"idempotency_key": idempotency_key})
        await _complete_order_idempotency(db, idempotency_key, str(created["_id"]))
    except Exception:
        await db["order_idempotency"].delete_one({"key": idempotency_key, "status": "in_progress"})
        raise
    if request:
        await track_event(
            db,
            "order_completed",
            user_id=user_id,
            order_id=str(created["_id"]),
            metadata={
                "total_amount": created["total_amount"],
                "payment_method": created.get("payment_method"),
                "items": created.get("item_snapshots", []),
            },
            request=request,
        )
    if background_tasks and meta_enqueued:
        background_tasks.add_task(process_meta_outbox_operation, db, f"meta:purchase:{created['_id']}")
    return _order_doc_to_out(created)


async def get_order_or_404(db, order_id: str) -> dict:
    order = await db["orders"].find_one({"_id": _parse_oid(order_id, "Commande ID")})
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    return order


async def transition_order_status(db, order_id: str, new_status: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await get_order_or_404(db, order_id)
    current_status = order.get("order_status", order.get("status"))
    ensure_order_transition(current_status, new_status)
    fulfillment_status = fulfillment_status_for_order_status(new_status, order.get("fulfillment_status"))
    await db["orders"].update_one(
        {"_id": order["_id"]},
        {
            "$set": {
                "status": new_status,
                "order_status": new_status,
                "fulfillment_status": fulfillment_status,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    await append_history(
        db,
        order_id=order_id,
        event_type="order_status_changed",
        from_order_status=current_status,
        to_order_status=new_status,
        from_payment_status=order.get("payment_status"),
        to_payment_status=order.get("payment_status"),
        from_fulfillment_status=order.get("fulfillment_status"),
        to_fulfillment_status=fulfillment_status,
        reason=reason,
        changed_by=actor_id,
        actor_type=actor_type,
    )
    return await get_order_or_404(db, order_id)


async def confirm_order(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await transition_order_status(db, order_id, ORDER_STATUS_CONFIRMED, actor_type=actor_type, actor_id=actor_id, reason=reason)
    await outbox_service.enqueue(db, event_type="order_confirmed", aggregate_type="order", aggregate_id=order_id, operation_key=f"order:{order_id}:confirmed", payload={"order_id": order_id})
    return _order_doc_to_out(order)


async def prepare_order(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await transition_order_status(db, order_id, ORDER_STATUS_PREPARING, actor_type=actor_type, actor_id=actor_id, reason=reason)
    return _order_doc_to_out(order)


async def ship_order(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await get_order_or_404(db, order_id)
    current_status = order.get("order_status", order.get("status"))
    ensure_order_transition(current_status, ORDER_STATUS_SHIPPED)
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            for index, allocation in enumerate(order.get("inventory_allocations", [])):
                await _fulfill_allocation(session, db, allocation, order_id, str(index))
            await db["orders"].update_one(
                {"_id": order["_id"]},
                {"$set": {"status": ORDER_STATUS_SHIPPED, "order_status": ORDER_STATUS_SHIPPED, "fulfillment_status": FULFILLMENT_STATUS_FULFILLED, "updated_at": datetime.utcnow()}},
                session=session,
            )
    await append_history(
        db,
        order_id=order_id,
        event_type="order_shipped",
        from_order_status=current_status,
        to_order_status=ORDER_STATUS_SHIPPED,
        from_payment_status=order.get("payment_status"),
        to_payment_status=order.get("payment_status"),
        from_fulfillment_status=order.get("fulfillment_status"),
        to_fulfillment_status=FULFILLMENT_STATUS_FULFILLED,
        reason=reason,
        changed_by=actor_id,
        actor_type=actor_type,
    )
    await outbox_service.enqueue(db, event_type="order_shipped", aggregate_type="order", aggregate_id=order_id, operation_key=f"order:{order_id}:shipped", payload={"order_id": order_id})
    return _order_doc_to_out(await get_order_or_404(db, order_id))


async def deliver_order(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await transition_order_status(db, order_id, ORDER_STATUS_DELIVERED, actor_type=actor_type, actor_id=actor_id, reason=reason)
    await outbox_service.enqueue(db, event_type="order_delivered", aggregate_type="order", aggregate_id=order_id, operation_key=f"order:{order_id}:delivered", payload={"order_id": order_id})
    return _order_doc_to_out(order)


async def cancel_order(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None, current_user_id: Optional[str] = None):
    order = await get_order_or_404(db, order_id)
    current_status = order.get("order_status", order.get("status"))
    if current_status == ORDER_STATUS_CANCELLED:
        raise OrderAlreadyCancelledError()
    ensure_order_transition(current_status, ORDER_STATUS_CANCELLED)
    if current_user_id and order.get("user_id") != current_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez annuler que vos propres commandes")

    async with await db.client.start_session() as session:
        async with session.start_transaction():
            if current_status in {ORDER_STATUS_PENDING, ORDER_STATUS_CONFIRMED, ORDER_STATUS_PREPARING}:
                for index, allocation in enumerate(order.get("inventory_allocations", [])):
                    await _release_allocation(session, db, allocation, order_id, str(index), reason or "order_cancelled")
            if order.get("promo_code") and order.get("user_id"):
                await promo_crud.release_use(db, order["promo_code"], order.get("user_id"), session=session)
            await refund_redeemed_points(db, order, reason="Annulation commande", session=session)
            await db["orders"].update_one(
                {"_id": order["_id"]},
                {
                    "$set": {
                        "status": ORDER_STATUS_CANCELLED,
                        "order_status": ORDER_STATUS_CANCELLED,
                        "fulfillment_status": FULFILLMENT_STATUS_CANCELLED,
                        "cancelled_at": datetime.utcnow(),
                        "cancelled_by": _actor_ref(actor_type, actor_id),
                        "cancellation_reason": reason,
                        "updated_at": datetime.utcnow(),
                    }
                },
                session=session,
            )
    await append_history(
        db,
        order_id=order_id,
        event_type="order_cancelled",
        from_order_status=current_status,
        to_order_status=ORDER_STATUS_CANCELLED,
        from_payment_status=order.get("payment_status"),
        to_payment_status=order.get("payment_status"),
        from_fulfillment_status=order.get("fulfillment_status"),
        to_fulfillment_status=FULFILLMENT_STATUS_CANCELLED,
        reason=reason,
        changed_by=actor_id,
        actor_type=actor_type,
    )
    await outbox_service.enqueue(db, event_type="order_cancelled", aggregate_type="order", aggregate_id=order_id, operation_key=f"order:{order_id}:cancelled", payload={"order_id": order_id})
    return _order_doc_to_out(await get_order_or_404(db, order_id))


async def mark_paid(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, payment_reference: Optional[str] = None, reason: Optional[str] = None):
    order = await get_order_or_404(db, order_id)
    if order.get("order_status", order.get("status")) in {ORDER_STATUS_CANCELLED, ORDER_STATUS_RETURNED}:
        raise InvalidOrderTransitionError("Impossible de marquer comme payee une commande annulee ou retournee")
    if order.get("payment_status") == PAYMENT_STATUS_PAID:
        return _order_doc_to_out(order)
    if order.get("payment_status") == PAYMENT_STATUS_REFUNDED:
        raise OrderAlreadyPaidError("La commande a deja ete remboursee")
    await db["orders"].update_one(
        {"_id": order["_id"]},
        {"$set": {"payment_status": PAYMENT_STATUS_PAID, "paid_at": datetime.utcnow(), "payment_reference": payment_reference, "updated_at": datetime.utcnow()}},
    )
    earned_points = await award_points_for_paid_order(db, order["_id"])
    await append_history(
        db,
        order_id=order_id,
        event_type="payment_marked_paid",
        from_order_status=order.get("order_status", order.get("status")),
        to_order_status=order.get("order_status", order.get("status")),
        from_payment_status=order.get("payment_status"),
        to_payment_status=PAYMENT_STATUS_PAID,
        from_fulfillment_status=order.get("fulfillment_status"),
        to_fulfillment_status=order.get("fulfillment_status"),
        reason=reason,
        changed_by=actor_id,
        actor_type=actor_type,
        metadata={"payment_reference": payment_reference, "loyalty_points_earned": earned_points},
    )
    await outbox_service.enqueue(db, event_type="payment_success", aggregate_type="order", aggregate_id=order_id, operation_key=f"order:{order_id}:paid", payload={"order_id": order_id})
    updated = await get_order_or_404(db, order_id)
    return _order_doc_to_out(updated)


async def request_return(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await transition_order_status(db, order_id, ORDER_STATUS_RETURN_REQUESTED, actor_type=actor_type, actor_id=actor_id, reason=reason)
    return _order_doc_to_out(order)


async def mark_return_in_transit(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await transition_order_status(db, order_id, ORDER_STATUS_RETURN_IN_TRANSIT, actor_type=actor_type, actor_id=actor_id, reason=reason)
    return _order_doc_to_out(order)


async def receive_return(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await transition_order_status(db, order_id, ORDER_STATUS_RETURN_RECEIVED, actor_type=actor_type, actor_id=actor_id, reason=reason)
    return _order_doc_to_out(order)


async def restock_returned_items(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await get_order_or_404(db, order_id)
    current_status = order.get("order_status", order.get("status"))
    if current_status not in {ORDER_STATUS_RETURN_RECEIVED, ORDER_STATUS_RETURNED}:
        raise InvalidOrderTransitionError("Le retour doit d'abord etre recu")
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            for index, allocation in enumerate(order.get("inventory_allocations", [])):
                qty = int(allocation["qty"])
                await db["products"].update_one(
                    {"_id": _parse_oid(allocation["product_id"], "Produit ID"), "variants.color": allocation["color"]},
                    {"$inc": {"variants.$.sizes.$[s].stock_on_hand": qty}},
                    array_filters=[{"s.size": allocation["size"]}],
                    session=session,
                )
                await _insert_inventory_movement(session, db, movement_type=INVENTORY_MOVEMENT_RETURN_RESTOCKED, allocation=allocation, order_id=order_id, order_item_key=str(index), on_hand_delta=qty, reserved_delta=0, reason=reason or "return_restocked", source="order_workflow")
            await db["orders"].update_one(
                {"_id": order["_id"]},
                {"$set": {"status": ORDER_STATUS_RETURNED, "order_status": ORDER_STATUS_RETURNED, "fulfillment_status": FULFILLMENT_STATUS_RETURNED, "updated_at": datetime.utcnow()}},
                session=session,
            )
    await append_history(
        db,
        order_id=order_id,
        event_type="return_restocked",
        from_order_status=current_status,
        to_order_status=ORDER_STATUS_RETURNED,
        from_payment_status=order.get("payment_status"),
        to_payment_status=order.get("payment_status"),
        from_fulfillment_status=order.get("fulfillment_status"),
        to_fulfillment_status=FULFILLMENT_STATUS_RETURNED,
        reason=reason,
        changed_by=actor_id,
        actor_type=actor_type,
    )
    return _order_doc_to_out(await get_order_or_404(db, order_id))


async def mark_return_damaged(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, reason: Optional[str] = None):
    order = await get_order_or_404(db, order_id)
    current_status = order.get("order_status", order.get("status"))
    if current_status != ORDER_STATUS_RETURN_RECEIVED:
        raise InvalidOrderTransitionError("Le retour doit etre recu avant evaluation")
    async with await db.client.start_session() as session:
        async with session.start_transaction():
            for index, allocation in enumerate(order.get("inventory_allocations", [])):
                await _insert_inventory_movement(session, db, movement_type=INVENTORY_MOVEMENT_RETURN_DAMAGED, allocation=allocation, order_id=order_id, order_item_key=str(index), on_hand_delta=0, reserved_delta=0, reason=reason or "return_damaged", source="order_workflow")
            await db["orders"].update_one(
                {"_id": order["_id"]},
                {"$set": {"status": ORDER_STATUS_RETURNED, "order_status": ORDER_STATUS_RETURNED, "fulfillment_status": FULFILLMENT_STATUS_RETURNED, "updated_at": datetime.utcnow()}},
                session=session,
            )
    await append_history(
        db,
        order_id=order_id,
        event_type="return_damaged",
        from_order_status=current_status,
        to_order_status=ORDER_STATUS_RETURNED,
        from_payment_status=order.get("payment_status"),
        to_payment_status=order.get("payment_status"),
        from_fulfillment_status=order.get("fulfillment_status"),
        to_fulfillment_status=FULFILLMENT_STATUS_RETURNED,
        reason=reason,
        changed_by=actor_id,
        actor_type=actor_type,
    )
    return _order_doc_to_out(await get_order_or_404(db, order_id))


async def refund_order(db, order_id: str, *, actor_type: str, actor_id: Optional[str] = None, amount: Optional[float] = None, reason: Optional[str] = None):
    order = await get_order_or_404(db, order_id)
    if order.get("payment_status") not in {PAYMENT_STATUS_PAID, PAYMENT_STATUS_PARTIALLY_REFUNDED}:
        raise InvalidOrderTransitionError("La commande n'est pas dans un etat remboursable")
    refund_amount = round(float(amount if amount is not None else order.get("total_amount", 0)), 2)
    new_refunded_amount = round(float(order.get("refunded_amount", 0) or 0) + refund_amount, 2)
    new_payment_status = payment_status_after_refund(new_refunded_amount, float(order.get("total_amount", 0) or 0))
    await db["orders"].update_one(
        {"_id": order["_id"]},
        {"$set": {"payment_status": new_payment_status, "refunded_amount": new_refunded_amount, "updated_at": datetime.utcnow()}},
    )
    await append_history(
        db,
        order_id=order_id,
        event_type="order_refunded",
        from_order_status=order.get("order_status", order.get("status")),
        to_order_status=order.get("order_status", order.get("status")),
        from_payment_status=order.get("payment_status"),
        to_payment_status=new_payment_status,
        from_fulfillment_status=order.get("fulfillment_status"),
        to_fulfillment_status=order.get("fulfillment_status"),
        reason=reason,
        changed_by=actor_id,
        actor_type=actor_type,
        metadata={"refund_amount": refund_amount},
    )
    await outbox_service.enqueue(db, event_type="order_refunded", aggregate_type="order", aggregate_id=order_id, operation_key=f"order:{order_id}:refund:{new_refunded_amount}", payload={"order_id": order_id, "refund_amount": refund_amount})
    return _order_doc_to_out(await get_order_or_404(db, order_id))
