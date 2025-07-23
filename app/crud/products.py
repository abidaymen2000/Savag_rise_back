from bson import ObjectId
from ..schemas import ProductCreate
from fastapi.encoders import jsonable_encoder

async def get_product(db, product_id: str):
    return await db["products"].find_one({"_id": ObjectId(product_id)})

async def get_products(db, skip: int = 0, limit: int = 10):
    cursor = db["products"].find().skip(skip).limit(limit)
    return await cursor.to_list(length=limit)

async def create_product(db, product: ProductCreate):
    # Convertit BaseModel, HttpUrl, etc. en dicts/str/int natifs
    doc = jsonable_encoder(product)
    res = await db["products"].insert_one(doc)
    return await db["products"].find_one({"_id": res.inserted_id})
