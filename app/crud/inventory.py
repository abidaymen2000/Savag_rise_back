from datetime import datetime


MOVEMENTS_COLLECTION = "inventory_movements"


async def list_inventory_items(db, filters, skip, limit):
    pipeline = [
        {"$unwind": "$variants"},
        {"$unwind": "$variants.sizes"},
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "full_name": 1,
                "sku": 1,
                "in_stock": 1,
                "color": "$variants.color",
                "size": "$variants.sizes.size",
                "stock_on_hand": "$variants.sizes.stock_on_hand",
                "stock_reserved": {"$ifNull": ["$variants.sizes.stock_reserved", 0]},
            }
        },
        {"$addFields": {"stock_available": {"$subtract": ["$stock_on_hand", "$stock_reserved"]}}},
    ]
    if filters:
        pipeline.append({"$match": filters})
    pipeline.extend([
        {"$sort": {"stock_available": 1, "full_name": 1}},
        {"$skip": skip},
        {"$limit": limit},
    ])
    return await db["products"].aggregate(pipeline).to_list(length=limit)


async def count_inventory_items(db, filters):
    pipeline = [
        {"$unwind": "$variants"},
        {"$unwind": "$variants.sizes"},
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "full_name": 1,
                "sku": 1,
                "in_stock": 1,
                "color": "$variants.color",
                "size": "$variants.sizes.size",
                "stock_on_hand": "$variants.sizes.stock_on_hand",
                "stock_reserved": {"$ifNull": ["$variants.sizes.stock_reserved", 0]},
            }
        },
        {"$addFields": {"stock_available": {"$subtract": ["$stock_on_hand", "$stock_reserved"]}}},
    ]
    if filters:
        pipeline.append({"$match": filters})
    pipeline.append({"$count": "total"})
    rows = await db["products"].aggregate(pipeline).to_list(length=1)
    return int(rows[0]["total"]) if rows else 0


async def find_variant_size(db, product_id, color, size):
    return await db["products"].find_one(
        {"_id": product_id, "variants": {"$elemMatch": {"color": color, "sizes": {"$elemMatch": {"size": size}}}}},
        {"name": 1, "full_name": 1, "variants.$": 1},
    )


async def set_variant_stock(db, product_id, color, size, new_stock_on_hand):
    return await db["products"].update_one(
        {"_id": product_id, "variants.color": color},
        {"$set": {"variants.$.sizes.$[s].stock_on_hand": new_stock_on_hand, "updated_at": datetime.utcnow()}},
        array_filters=[{"s.size": size}],
    )


async def insert_movement(db, data):
    return await db[MOVEMENTS_COLLECTION].insert_one(data)


async def list_movements(db, filters, skip, limit):
    return await db[MOVEMENTS_COLLECTION].find(filters).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)


async def count_movements(db, filters):
    return await db[MOVEMENTS_COLLECTION].count_documents(filters)
