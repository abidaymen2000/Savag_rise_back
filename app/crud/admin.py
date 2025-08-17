from typing import Optional
from datetime import datetime
from app.db import client
from app.models.admin import AdminInDB

COL = client.get_default_database()["admins"]

async def get_by_email(email: str) -> Optional[AdminInDB]:
    doc = await COL.find_one({"email": email})
    return AdminInDB(**doc) if doc else None

async def create(admin: AdminInDB) -> AdminInDB:
    admin.updated_at = datetime.utcnow()
    res = await COL.insert_one(admin.model_dump(by_alias=True))
    admin.id = str(res.inserted_id)
    return admin
