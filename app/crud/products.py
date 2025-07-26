from bson import ObjectId
from fastapi.encoders import jsonable_encoder
from ..schemas.product import ProductCreate, ProductUpdate

async def get_product(db, product_id: str):
    return await db["products"].find_one({"_id": ObjectId(product_id)})

async def get_products(db, skip: int = 0, limit: int = 10):
    cursor = db["products"].find().skip(skip).limit(limit)
    return await cursor.to_list(length=limit)

async def create_product(db, product: ProductCreate):
    doc = jsonable_encoder(product)
    res = await db["products"].insert_one(doc)
    return await db["products"].find_one({"_id": res.inserted_id})

async def update_product(db, product_id: str, data: ProductUpdate):
    oid = ObjectId(product_id)
    upd = data.dict(exclude_unset=True)
    if upd:
        await db["products"].update_one({"_id": oid}, {"$set": upd})
    return await db["products"].find_one({"_id": oid})

async def delete_product(db, product_id: str):
    oid = ObjectId(product_id)
    await db["products"].delete_one({"_id": oid})
