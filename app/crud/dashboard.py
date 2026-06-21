from datetime import datetime


async def count_orders(db, filters=None):
    return await db["orders"].count_documents(filters or {})


async def summarize_order_revenue(db, filters=None):
    rows = await db["orders"].aggregate([
        {"$match": filters or {}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}, "average": {"$avg": "$total_amount"}}},
    ]).to_list(length=1)
    return rows[0] if rows else {}


async def summarize_revenue_for_period(db, start: datetime):
    rows = await db["orders"].aggregate([
        {
            "$match": {
                "created_at": {"$gte": start},
                "status": {"$ne": "cancelled"},
            }
        },
        {
            "$group": {
                "_id": None,
                "revenue": {"$sum": "$total_amount"},
                "orders": {"$sum": 1},
                "average_order": {"$avg": "$total_amount"},
            }
        },
    ]).to_list(length=1)
    return rows[0] if rows else {}


async def aggregate_top_product_sales(db, limit):
    return await db["orders"].aggregate([
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.product_id",
                "qty": {"$sum": "$items.qty"},
                "revenue": {"$sum": {"$multiply": ["$items.qty", "$items.unit_price"]}},
            }
        },
        {"$sort": {"qty": -1}},
        {"$limit": limit},
    ]).to_list(length=limit)


async def list_product_names_by_ids(db, product_ids):
    return await db["products"].find(
        {"_id": {"$in": product_ids}},
        {"name": 1, "full_name": 1},
    ).to_list(length=len(product_ids))


async def list_low_stock_items(db, threshold, limit):
    return await db["products"].aggregate([
        {"$unwind": "$variants"},
        {"$unwind": "$variants.sizes"},
        {"$match": {"variants.sizes.stock": {"$lte": threshold}}},
        {"$sort": {"variants.sizes.stock": 1}},
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "full_name": 1,
                "color": "$variants.color",
                "size": "$variants.sizes.size",
                "stock": "$variants.sizes.stock",
            }
        },
        {"$limit": limit},
    ]).to_list(length=limit)


async def count_low_stock_items(db, threshold):
    rows = await db["products"].aggregate([
        {"$unwind": "$variants"},
        {"$unwind": "$variants.sizes"},
        {"$match": {"variants.sizes.stock": {"$lte": threshold}}},
        {"$count": "total"},
    ]).to_list(length=1)
    return int(rows[0]["total"]) if rows else 0


async def distinct_order_user_ids(db, filters):
    return await db["orders"].distinct("user_id", filters)


async def count_collection(db, collection, filters=None):
    return await db[collection].count_documents(filters or {})
