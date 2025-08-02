# app/crud/category.py

from datetime import datetime
from bson import ObjectId
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase

async def list_categories(db: AsyncIOMotorDatabase) -> List[dict]:
    return await db["categories"].find().to_list(length=100)

async def get_category(db: AsyncIOMotorDatabase, category_id: str) -> dict:
    return await db["categories"].find_one({"_id": ObjectId(category_id)})

async def create_category(db: AsyncIOMotorDatabase, data: dict) -> dict:
    payload = {
        **data,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    res = await db["categories"].insert_one(payload)
    return await db["categories"].find_one({"_id": res.inserted_id})

async def update_category(db: AsyncIOMotorDatabase, category_id: str, data: dict) -> dict:
    oid = ObjectId(category_id)
    data["updated_at"] = datetime.utcnow()
    await db["categories"].update_one({"_id": oid}, {"$set": data})
    return await db["categories"].find_one({"_id": oid})

async def delete_category(db: AsyncIOMotorDatabase, category_id: str) -> None:
    await db["categories"].delete_one({"_id": ObjectId(category_id)})
