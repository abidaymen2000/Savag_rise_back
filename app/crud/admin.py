import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from app.db import client
from app.models.admin import AdminInDB
from app.config import settings

COL = client[settings.MONGODB_DB_NAME]["admins"]

def _norm_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

async def get_by_email(email: str) -> Optional[AdminInDB]:
    data = await COL.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
    data = _norm_id(data)
    return AdminInDB(**data) if data else None


async def get_by_id(admin_id: str) -> Optional[AdminInDB]:
    data = await COL.find_one({"_id": ObjectId(admin_id)})
    data = _norm_id(data)
    return AdminInDB(**data) if data else None


async def list_admins(filters: Dict[str, Any], skip: int, limit: int) -> List[AdminInDB]:
    docs = await COL.find(filters).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return [AdminInDB(**_norm_id(doc)) for doc in docs]


async def count_admins(filters: Dict[str, Any]) -> int:
    return await COL.count_documents(filters)

async def create(admin: AdminInDB) -> AdminInDB:
    admin.updated_at = datetime.utcnow()
    res = await COL.insert_one(admin.model_dump(by_alias=True))
    admin.id = str(res.inserted_id)
    return admin


async def update_admin(admin_id: str, data: Dict[str, Any]) -> Optional[AdminInDB]:
    if not data:
        return await get_by_id(admin_id)
    data["updated_at"] = datetime.utcnow()
    await COL.update_one({"_id": ObjectId(admin_id)}, {"$set": data})
    return await get_by_id(admin_id)


async def delete_admin(admin_id: str) -> bool:
    res = await COL.delete_one({"_id": ObjectId(admin_id)})
    return res.deleted_count == 1

async def update_password_hash(email: str, password_hash: str) -> bool:
    res = await COL.update_one(
        {"email": email},
        {"$set": {"password_hash": password_hash, "updated_at": datetime.utcnow()}}
    )
    return res.modified_count == 1
