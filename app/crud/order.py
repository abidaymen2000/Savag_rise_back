from datetime import datetime
from typing import Any, Dict, List, Tuple

from bson import ObjectId
from fastapi import HTTPException, status


async def get_order(db, order_id: ObjectId):
    doc = await db["orders"].find_one({"_id": order_id})
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    return doc


async def delete_order_by_id(db, order_id: ObjectId):
    return await db["orders"].delete_one({"_id": order_id})


async def push_order_field(db, order_id: ObjectId, field: str, value: dict):
    await db["orders"].update_one(
        {"_id": order_id},
        {"$push": {field: value}, "$set": {"updated_at": datetime.utcnow()}},
    )


async def set_order_fields(db, order_id: ObjectId, data: dict):
    data["updated_at"] = datetime.utcnow()
    await db["orders"].update_one({"_id": order_id}, {"$set": data})


async def get_orders_for_user(db, user_id: str):
    cursor = db["orders"].find({"user_id": user_id}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    result = []
    for d in docs:
        d["id"] = str(d["_id"])
        result.append(d)
    return result


def parse_oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID de commande invalide")


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
    sort: Tuple[str, int] = ("_id", -1),
) -> List[Dict[str, Any]]:
    cursor = db["orders"].find(filters).skip(skip).limit(limit).sort([sort])
    return [_normalize(x) async for x in cursor]


async def count_orders(db, filters: Dict[str, Any]) -> int:
    return await db["orders"].count_documents(filters)
