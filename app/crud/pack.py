PACKS_COLLECTION = "packs"


async def find_product_by_id(db, product_id):
    return await db["products"].find_one({"_id": product_id})


async def count_products_by_ids(db, product_ids):
    return await db["products"].count_documents({"_id": {"$in": product_ids}})


async def find_pack_by_id(db, pack_id):
    return await db[PACKS_COLLECTION].find_one({"_id": pack_id})


async def list_packs(db, filters, skip, limit):
    return await db[PACKS_COLLECTION].find(filters).sort("order", 1).skip(skip).limit(limit).to_list(length=limit)


async def count_packs(db, filters):
    return await db[PACKS_COLLECTION].count_documents(filters)


async def insert_pack(db, data):
    return await db[PACKS_COLLECTION].insert_one(data)


async def update_pack(db, pack_id, data):
    return await db[PACKS_COLLECTION].update_one({"_id": pack_id}, {"$set": data})


async def delete_pack(db, pack_id):
    return await db[PACKS_COLLECTION].delete_one({"_id": pack_id})
