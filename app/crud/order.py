# app/crud/order.py
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException,status


async def create_order(db, order_data: dict):
    """
    Crée une commande en base :
    - order_data doit contenir au minimum les clés :
       'user_id', 'shipping', 'items', 'payment_method'
    - 'shipping' est un dict contenant full_name, email, phone, address_line1, etc.
    - 'items' est une liste de dict { product_id, color, size, qty, unit_price }
    """
    now = datetime.utcnow()
    # Construction du document à insérer
    order_doc = {
        "user_id": order_data.get("user_id"),             # lien vers l'user
        "shipping": order_data["shipping"],               # adresse + contact
        "items": order_data["items"],                     # lignes de commande
        "payment_method": order_data.get("payment_method", "cod"),
        "total_amount": sum(i["unit_price"] * i["qty"] for i in order_data["items"]),
        "status": "pending",                              # nouvelle commande
        "payment_status": "unpaid",                       # COD non encaissé
        "created_at": now,
        "updated_at": now,
    }
    # Insertion et récupération de l'_id
    res = await db["orders"].insert_one(order_doc)
    # On rattache l'id stringifié pour le retour
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