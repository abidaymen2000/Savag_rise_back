# app/crud/user_admin.py
from typing import Dict, Any, List, Tuple, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

def _norm(doc: dict) -> dict:
    if not doc:
        return doc
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc

async def list_users(
    db: AsyncIOMotorDatabase,
    filters: Dict[str, Any],
    skip: int,
    limit: int,
    sort: Tuple[str, int] = ("_id", -1),
) -> List[Dict[str, Any]]:
    # Ne remonte que les champs utiles à l’admin (évite de renvoyer hash/méta sensibles)
    projection = {
        "email": 1,
        "full_name": 1,
        "is_active": 1,
        "created_at": 1,
        "last_login_at": 1,   # si tu l’as
    }
    cursor = (
        db["users"]
        .find(filters, projection)
        .skip(skip)
        .limit(limit)
        .sort([sort])
    )
    return [_norm(x) async for x in cursor]

async def count_users(db: AsyncIOMotorDatabase, filters: Dict[str, Any]) -> int:
    return await db["users"].count_documents(filters)

async def get_user(db: AsyncIOMotorDatabase, user_id: ObjectId) -> Optional[Dict[str, Any]]:
    doc = await db["users"].find_one({"_id": user_id})
    return _norm(doc) if doc else None

async def set_user_active(
    db: AsyncIOMotorDatabase, user_id: ObjectId, is_active: bool
) -> bool:
    res = await db["users"].update_one(
        {"_id": user_id},
        {"$set": {"is_active": is_active}}
    )
    return res.matched_count == 1
