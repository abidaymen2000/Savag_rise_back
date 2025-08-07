# app/crud/review.py
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

async def create_review(db: AsyncIOMotorDatabase, product_id: str, data: dict):
    doc = {
        **data,
        "product_id": product_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    res = await db["reviews"].insert_one(doc)
    return await db["reviews"].find_one({"_id": res.inserted_id})

async def get_review(db, product_id: str, review_id: str):
    return await db["reviews"].find_one({
        "_id": ObjectId(review_id),
        "product_id": product_id
    })

async def update_review(db, product_id: str, review_id: str, data: dict):
    data["updated_at"] = datetime.utcnow()
    await db["reviews"].update_one(
        {"_id": ObjectId(review_id), "product_id": product_id},
        {"$set": data}
    )
    return await get_review(db, product_id, review_id)

async def delete_review(db, product_id: str, review_id: str):
    await db["reviews"].delete_one({
        "_id": ObjectId(review_id),
        "product_id": product_id
    })

async def list_reviews(db, product_id: str, rating: int = None, skip: int = 0, limit: int = 10, sort_best: bool = False):
    filt = {"product_id": product_id}
    if rating:
        filt["rating"] = rating
    cursor = db["reviews"].find(filt)
    if sort_best:
        cursor = cursor.sort("rating", -1)
    else:
        cursor = cursor.sort("created_at", -1)
    return await cursor.skip(skip).to_list(length=limit)

async def get_review_stats(db, product_id: str):
    pipeline = [
        {"$match": {"product_id": product_id}},
        {"$group": {
            "_id": "$product_id",
            "average_rating": {"$avg": "$rating"},
            "count": {"$sum": 1}
        }}
    ]
    res = await db["reviews"].aggregate(pipeline).to_list(length=1)
    if res:
        return {"average_rating": res[0]["average_rating"], "count": res[0]["count"]}
    return {"average_rating": None, "count": 0}

async def list_user_reviews(
    db: AsyncIOMotorDatabase,
    user_id: str,
    skip: int = 0,
    limit: int = 10
):
    """
    Renvoie la liste des reviews pour un user donné.
    """
    cursor = db["reviews"].find({"user_id": user_id})
    return await cursor.sort("created_at", -1).skip(skip).to_list(length=limit)
