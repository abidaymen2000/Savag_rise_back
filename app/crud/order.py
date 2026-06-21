# app/crud/order.py
from datetime import datetime
from typing import Any, Dict, List, Tuple
from bson import ObjectId
from fastapi import HTTPException,status


async def create_order(db, order_data: dict):
    """
    Crée une commande en base.
    Respecte les champs calculés par le routeur si fournis:
    - subtotal, discount_value, promo_code, total_amount
    Sinon, calcule un subtotal et met total_amount = subtotal.
    """
    now = datetime.utcnow()

    # 1) Champs requis
    user_id = order_data.get("user_id")
    user_email = order_data.get("user_email")
    is_guest = order_data.get("is_guest", user_id is None)
    shipping = order_data["shipping"]
    items = order_data["items"]
    payment_method = order_data.get("payment_method", "cod")
    pack_items = order_data.get("pack_items", [])

    # 2) Subtotal (si non fourni)
    subtotal = order_data.get("subtotal")
    if subtotal is None:
        subtotal = sum(i["unit_price"] * i["qty"] for i in items)

    # 3) Total & remise
    total_amount = order_data.get("total_amount", subtotal)
    discount_value = order_data.get("discount_value")
    if discount_value is None:
        # calcule implicite si on ne l'a pas passé
        discount_value = max(0.0, float(subtotal) - float(total_amount))

    # 4) Code promo (optionnel)
    promo_code = order_data.get("promo_code")
    pack_discount_value = float(order_data.get("pack_discount_value", 0) or 0)
    shipping_amount = order_data.get("shipping_amount", 0)
    shipping_rate_id = order_data.get("shipping_rate_id")
    shipping_rate_name = order_data.get("shipping_rate_name")
    loyalty_points_to_use = int(order_data.get("loyalty_points_to_use", 0) or 0)
    loyalty_points_used = int(order_data.get("loyalty_points_used", 0) or 0)
    loyalty_discount_value = float(order_data.get("loyalty_discount_value", 0) or 0)
    loyalty_eligible_amount = float(order_data.get("loyalty_eligible_amount", subtotal) or 0)

    # 5) Construction du document
    order_doc = {
        "user_id": user_id,
        "user_email": user_email,
        "is_guest": is_guest,
        "shipping": shipping,
        "items": items,
        "pack_items": pack_items,
        "payment_method": payment_method,

        # Remises / totaux
        "subtotal": float(subtotal),
        "discount_value": float(discount_value),
        "pack_discount_value": pack_discount_value,
        "promo_code": promo_code,
        "loyalty_points_to_use": loyalty_points_to_use,
        "loyalty_points_used": loyalty_points_used,
        "loyalty_discount_value": loyalty_discount_value,
        "loyalty_eligible_amount": loyalty_eligible_amount,
        "loyalty_points_earned": 0,
        "loyalty_points_awarded": False,
        "loyalty_points_refunded": False,
        "shipping_amount": float(shipping_amount),
        "shipping_rate_id": shipping_rate_id,
        "shipping_rate_name": shipping_rate_name,
        "total_amount": float(total_amount),

        # Statuts
        "status": "pending",
        "payment_status": "unpaid",

        # Dates
        "created_at": now,
        "updated_at": now,
    }

    # 6) Insertion
    res = await db["orders"].insert_one(order_doc)
    order_doc["id"] = str(res.inserted_id)
    return order_doc


async def get_order(db, order_id: ObjectId):
    """
    Renvoie la commande (JSON-like dict) ou None si introuvable.
    """
    doc = await db["orders"].find_one({"_id": order_id})
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    return doc


async def delete_order_by_id(db, order_id: ObjectId):
    return await db["orders"].delete_one({"_id": order_id})


async def update_order_status(db, order_id: ObjectId, new_status: str):
    """
    Change le champ 'status' (p.ex. pending → shipped → delivered).
    """
    await db["orders"].update_one(
        {"_id": order_id},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )


async def push_order_field(db, order_id: ObjectId, field: str, value: dict):
    await db["orders"].update_one(
        {"_id": order_id},
        {"$push": {field: value}, "$set": {"updated_at": datetime.utcnow()}},
    )


async def set_order_fields(db, order_id: ObjectId, data: dict):
    data["updated_at"] = datetime.utcnow()
    await db["orders"].update_one({"_id": order_id}, {"$set": data})


async def mark_paid(db, order_id: ObjectId):
    """
    Marque la commande comme payée (en COD c'est au moment de la livraison).
    """
    await db["orders"].update_one(
        {"_id": order_id},
        {"$set": {"payment_status": "paid", "updated_at": datetime.utcnow()}}
    )
    
async def get_orders_for_user(db, user_id: str):
    cursor = db["orders"].find({"user_id": user_id}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    # on transforme _id → id et renvoie le modèle
    result = []
    for d in docs:
        d["id"] = str(d["_id"])
        result.append(d)
    return result

def parse_oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID de commande invalide")
    
    
    # --- LISTING ADMIN ---
def _normalize(doc: dict) -> dict:
    if not doc:
        return doc
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc

async def list_orders(
    db,
    filters: Dict[str, Any],
    skip: int,
    limit: int,
    sort: Tuple[str, int] = ("_id", -1),   # -1 = desc (les plus récentes d'abord)
) -> List[Dict[str, Any]]:
    cursor = (
        db["orders"]
        .find(filters)
        .skip(skip)
        .limit(limit)
        .sort([sort])
    )
    return [_normalize(x) async for x in cursor]

async def count_orders(db, filters: Dict[str, Any]) -> int:
    return await db["orders"].count_documents(filters)
