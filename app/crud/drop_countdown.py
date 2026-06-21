DROP_COUNTDOWN_KEY = "store_drop_countdown"
SETTINGS_COLLECTION = "cms_settings"
SUBSCRIBERS_COLLECTION = "drop_notification_subscribers"


async def find_drop_doc(db):
    return await db[SETTINGS_COLLECTION].find_one({"_id": DROP_COUNTDOWN_KEY})


async def count_subscribers(db, filters):
    return await db[SUBSCRIBERS_COLLECTION].count_documents(filters)


async def find_subscription(db, drop_key, user_id):
    return await db[SUBSCRIBERS_COLLECTION].find_one({"drop_key": drop_key, "user_id": user_id})


async def upsert_subscription(db, drop_key, user_id, email, now):
    return await db[SUBSCRIBERS_COLLECTION].update_one(
        {"drop_key": drop_key, "user_id": user_id},
        {
            "$set": {"email": email, "updated_at": now},
            "$setOnInsert": {"drop_key": drop_key, "user_id": user_id, "created_at": now},
        },
        upsert=True,
    )


async def delete_subscription(db, drop_key, user_id):
    return await db[SUBSCRIBERS_COLLECTION].delete_one({"drop_key": drop_key, "user_id": user_id})


async def list_matching_user_ids(db, user_filters, limit=5000):
    return await db["users"].find(user_filters, {"_id": 1}).to_list(length=limit)


async def list_subscribers(db, filters, skip, limit):
    return await (
        db[SUBSCRIBERS_COLLECTION]
        .find(filters)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )


async def list_users_by_ids(db, user_ids):
    return await db["users"].find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))


async def save_drop_countdown(db, update):
    return await db[SETTINGS_COLLECTION].update_one(
        {"_id": DROP_COUNTDOWN_KEY},
        update,
        upsert=True,
    )


async def claim_due_drop_notification(db, now, stale_claim_before):
    return await db[SETTINGS_COLLECTION].find_one_and_update(
        {
            "_id": DROP_COUNTDOWN_KEY,
            "value.is_active": True,
            "value.email_enabled": True,
            "value.launch_at": {"$lte": now},
            "notification_sent_at": {"$exists": False},
            "$or": [
                {"notification_status": {"$exists": False}},
                {"notification_status": {"$ne": "sending"}},
                {"notification_claimed_at": {"$lte": stale_claim_before}},
            ],
        },
        {
            "$set": {
                "notification_status": "sending",
                "notification_claimed_at": now,
            }
        },
    )


async def list_drop_subscriptions(db, drop_key, limit=20000):
    return await db[SUBSCRIBERS_COLLECTION].find(
        {"drop_key": drop_key},
        {"user_id": 1, "email": 1},
    ).to_list(length=limit)


async def list_active_users_with_email(db, user_ids, limit=20000):
    return await db["users"].find(
        {
            "_id": {"$in": user_ids},
            "email": {"$exists": True, "$ne": None},
            "is_active": True,
        },
        {"email": 1},
    ).to_list(length=limit)


async def mark_drop_notification_sent(db, sent_count, failure_count, sent_at):
    return await db[SETTINGS_COLLECTION].update_one(
        {"_id": DROP_COUNTDOWN_KEY},
        {
            "$set": {
                "notification_status": "sent",
                "notification_sent_at": sent_at,
                "notification_recipients_count": sent_count,
                "notification_failures_count": failure_count,
            }
        },
    )
