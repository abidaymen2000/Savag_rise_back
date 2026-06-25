SETTINGS_COLLECTION = "cms_settings"
LOYALTY_SETTINGS_KEY = "loyalty_program"
TRANSACTIONS_COLLECTION = "loyalty_transactions"


async def find_loyalty_settings(db):
    return await db[SETTINGS_COLLECTION].find_one({"_id": LOYALTY_SETTINGS_KEY})


async def save_loyalty_settings(db, value, updated_at):
    return await db[SETTINGS_COLLECTION].update_one(
        {"_id": LOYALTY_SETTINGS_KEY},
        {"$set": {"value": value, "updated_at": updated_at}},
        upsert=True,
    )


async def find_user_points_balance(db, user_id):
    return await db["users"].find_one({"_id": user_id}, {"loyalty_points_balance": 1})


async def insert_loyalty_transaction(db, data, session=None):
    return await db[TRANSACTIONS_COLLECTION].insert_one(data, session=session)


async def list_loyalty_transactions(db, filters, skip=0, limit=20):
    return await (
        db[TRANSACTIONS_COLLECTION]
        .find(filters)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )


async def count_loyalty_transactions(db, filters):
    return await db[TRANSACTIONS_COLLECTION].count_documents(filters)


async def decrement_user_points_if_available(db, user_id, points, session=None):
    return await db["users"].find_one_and_update(
        {"_id": user_id, "loyalty_points_balance": {"$gte": points}},
        {"$inc": {"loyalty_points_balance": -points}},
        session=session,
        return_document=True,
    )


async def increment_user_points(db, user_id, points, session=None):
    return await db["users"].find_one_and_update(
        {"_id": user_id},
        {"$inc": {"loyalty_points_balance": points}},
        session=session,
        return_document=True,
    )


async def set_user_points_balance(db, user_id, balance):
    return await db["users"].update_one(
        {"_id": user_id},
        {"$set": {"loyalty_points_balance": balance}},
    )


async def mark_order_loyalty_points_refunded(db, order_id, session=None):
    return await db["orders"].update_one(
        {"_id": order_id},
        {"$set": {"loyalty_points_refunded": True}},
        session=session,
    )


async def find_order_by_id(db, order_id):
    return await db["orders"].find_one({"_id": order_id})


async def mark_order_loyalty_awarded(db, order_id, points, session=None):
    return await db["orders"].update_one(
        {"_id": order_id},
        {"$set": {"loyalty_points_awarded": True, "loyalty_points_earned": points}},
        session=session,
    )
