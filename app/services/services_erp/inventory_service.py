from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.pagination import build_page
from app.crud import inventory as inventory_crud
from app.domain.order_constants import INVENTORY_MOVEMENT_MANUAL
from app.schemas.inventory import InventoryItemOut, InventoryMovementOut
from app.services.services_erp.audit_service import log_action


def validate_oid(value: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} invalide")


def item_out(doc, threshold: int) -> InventoryItemOut:
    stock_on_hand = int(doc.get("stock_on_hand", 0) or 0)
    stock_reserved = int(doc.get("stock_reserved", 0) or 0)
    stock_available = int(doc.get("stock_available", stock_on_hand - stock_reserved) or 0)
    return InventoryItemOut(
        product_id=str(doc["_id"]),
        product_name=doc.get("full_name") or doc.get("name") or str(doc["_id"]),
        sku=doc.get("sku"),
        color=doc.get("color"),
        size=doc.get("size"),
        stock_on_hand=stock_on_hand,
        stock_reserved=stock_reserved,
        stock_available=stock_available,
        in_stock=doc.get("in_stock", True),
        low_stock=stock_available <= threshold,
    )


def movement_out(doc) -> InventoryMovementOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return InventoryMovementOut(**payload)


def inventory_filters(q: Optional[str], color: Optional[str], size: Optional[str], low_stock: Optional[bool], threshold: int):
    filters = {}
    if q:
        filters["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"full_name": {"$regex": q, "$options": "i"}},
            {"sku": {"$regex": q, "$options": "i"}},
        ]
    if color:
        filters["color"] = color
    if size:
        filters["size"] = size
    if low_stock is True:
        filters["stock_available"] = {"$lte": threshold}
    elif low_stock is False:
        filters["stock_available"] = {"$gt": threshold}
    return filters


async def list_inventory(db, pagination, q=None, color=None, size=None, low_stock=None, threshold: int = 5):
    filters = inventory_filters(q, color, size, low_stock, threshold)
    total = await inventory_crud.count_inventory_items(db, filters)
    docs = await inventory_crud.list_inventory_items(db, filters, pagination.skip, pagination.page_size)
    return build_page(
        items=[item_out(doc, threshold) for doc in docs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "stock_available", "dir": "asc"},
        filters={"q": q, "color": color, "size": size, "low_stock": low_stock, "threshold": threshold},
    )


def current_stock_from_product(product, color, size) -> tuple[int, int]:
    for variant in product.get("variants", []):
        if variant.get("color") != color:
            continue
        for row in variant.get("sizes", []):
            if row.get("size") == size:
                on_hand = int(row.get("stock_on_hand", 0) or 0)
                reserved = int(row.get("stock_reserved", 0) or 0)
                return on_hand, reserved
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Variante/taille introuvable")


async def adjust_stock(db, payload, admin):
    product_id = validate_oid(payload.product_id, "Produit ID")
    product = await inventory_crud.find_variant_size(db, product_id, payload.color, payload.size)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit ou variante introuvable")
    previous_on_hand, previous_reserved = current_stock_from_product(product, payload.color, payload.size)
    if payload.new_stock_on_hand is not None:
        new_on_hand = int(payload.new_stock_on_hand)
    elif payload.delta is not None:
        new_on_hand = max(0, previous_on_hand + int(payload.delta))
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "delta ou new_stock_on_hand est requis")

    delta = new_on_hand - previous_on_hand
    await inventory_crud.set_variant_stock(db, product_id, payload.color, payload.size, new_on_hand)
    now = datetime.utcnow()
    data = {
        "product_id": str(product_id),
        "product_name": product.get("full_name") or product.get("name"),
        "color": payload.color,
        "size": payload.size,
        "movement_type": INVENTORY_MOVEMENT_MANUAL,
        "on_hand_delta": delta,
        "reserved_delta": 0,
        "on_hand_before": previous_on_hand,
        "on_hand_after": new_on_hand,
        "reserved_before": previous_reserved,
        "reserved_after": previous_reserved,
        "reason": payload.reason,
        "source": "manual",
        "operation_key": f"manual:{product_id}:{payload.color}:{payload.size}:{int(now.timestamp())}",
        "admin_id": str(admin.id),
        "admin_email": admin.email,
        "metadata": {},
        "created_at": now,
    }
    res = await inventory_crud.insert_movement(db, data)
    await log_action(
        db,
        admin=admin,
        action="inventory.adjust",
        module="inventory",
        entity_type="product",
        entity_id=str(product_id),
        message=f"Stock ajuste {payload.color}/{payload.size}: {previous_on_hand} -> {new_on_hand}",
        metadata={"color": payload.color, "size": payload.size, "on_hand_delta": delta, "reason": payload.reason},
    )
    data["id"] = str(res.inserted_id)
    return InventoryMovementOut(**data)


async def list_movements(db, pagination, product_id=None, color=None, size=None, source=None):
    filters = {}
    if product_id:
        filters["product_id"] = product_id
    if color:
        filters["color"] = color
    if size:
        filters["size"] = size
    if source:
        filters["source"] = source
    total = await inventory_crud.count_movements(db, filters)
    docs = await inventory_crud.list_movements(db, filters, pagination.skip, pagination.page_size)
    return build_page(
        items=[movement_out(doc) for doc in docs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "created_at", "dir": "desc"},
        filters=filters,
    )
