# app/crud/wishlist.py
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

async def add_to_wishlist(db: AsyncIOMotorDatabase, user_id: str, product_id: str):
    doc = {
        "user_id": user_id,
        "product_id": product_id,
        "added_at": datetime.utcnow()
    }
    try:
        res = await db["wishlist"].insert_one(doc)
        return await db["wishlist"].find_one({"_id": res.inserted_id})
    except DuplicateKeyError:
        # l’élément existe déjà, on renvoie simplement l’existant
        return await db["wishlist"].find_one({"user_id": user_id, "product_id": product_id})

async def remove_from_wishlist(db: AsyncIOMotorDatabase, user_id: str, product_id: str):
    await db["wishlist"].delete_one({"user_id": user_id, "product_id": product_id})

async def list_wishlist(db: AsyncIOMotorDatabase, user_id: str, skip: int = 0, limit: int = 20):
    cursor = db["wishlist"]\
        .find({"user_id": user_id})\
        .sort("added_at", -1)\
        .skip(skip)\
        .limit(limit)
    return await cursor.to_list(length=limit)
