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
    shipping = order_data["shipping"]
    items = order_data["items"]
    payment_method = order_data.get("payment_method", "cod")

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

    # 5) Construction du document
    order_doc = {
        "user_id": user_id,
        "shipping": shipping,
        "items": items,
        "payment_method": payment_method,

        # Remises / totaux
        "subtotal": float(subtotal),
        "discount_value": float(discount_value),
        "promo_code": promo_code,
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


async def update_order_status(db, order_id: ObjectId, new_status: str):
    """
    Change le champ 'status' (p.ex. pending → shipped → delivered).
    """
    await db["orders"].update_one(
        {"_id": order_id},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )


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