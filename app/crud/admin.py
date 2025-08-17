from typing import Optional
from datetime import datetime
from app.db import client
from app.models.admin import AdminInDB

COL = client.get_default_database()["admins"]

def _norm_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

async def get_by_email(email: str) -> Optional[AdminInDB]:
    data = await COL.find_one({"email": email})
    data = _norm_id(data)
    return AdminInDB(**data) if data else None

async def create(admin: AdminInDB) -> AdminInDB:
    admin.updated_at = datetime.utcnow()
    res = await COL.insert_one(admin.model_dump(by_alias=True))
    admin.id = str(res.inserted_id)
    return admin
