SETTINGS_COLLECTION = "cms_settings"
VLOG_SETTINGS_KEY = "vlog_page"
CHAPTERS_COLLECTION = "vlog_chapters"
EPISODES_COLLECTION = "vlog_episodes"
LIKES_COLLECTION = "vlog_episode_likes"
COMMENTS_COLLECTION = "vlog_comments"


async def find_chapter_by_slug(db, slug, exclude_id=None):
    query = {"slug": slug}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    return await db[CHAPTERS_COLLECTION].find_one(query)


async def find_products_by_ids(db, product_ids):
    return await db["products"].find({"_id": {"$in": product_ids}}).to_list(length=len(product_ids))


async def count_episode_likes(db, episode_id):
    return await db[LIKES_COLLECTION].count_documents({"episode_id": episode_id})


async def count_visible_episode_comments(db, episode_id):
    return await db[COMMENTS_COLLECTION].count_documents({
        "episode_id": episode_id,
        "status": "visible",
    })


async def find_episode_like(db, episode_id, user_id):
    return await db[LIKES_COLLECTION].find_one({
        "episode_id": episode_id,
        "user_id": user_id,
    })


async def find_vlog_settings(db):
    return await db[SETTINGS_COLLECTION].find_one({"_id": VLOG_SETTINGS_KEY})


async def list_chapter_episodes(db, filters, limit=50):
    return await db[EPISODES_COLLECTION].find(filters).sort("order", 1).to_list(length=limit)


async def find_user_summary(db, user_id):
    return await db["users"].find_one(
        {"_id": user_id},
        {"full_name": 1, "email": 1},
    )


async def find_episode_summary(db, episode_id):
    return await db[EPISODES_COLLECTION].find_one(
        {"_id": episode_id},
        {"title": 1},
    )


async def count_comments(db, filters):
    return await db[COMMENTS_COLLECTION].count_documents(filters)


async def list_comments(db, filters, skip, limit):
    return await (
        db[COMMENTS_COLLECTION]
        .find(filters)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )


async def find_comment_by_id(db, comment_id):
    return await db[COMMENTS_COLLECTION].find_one({"_id": comment_id})


async def update_comment(db, comment_id, data):
    return await db[COMMENTS_COLLECTION].update_one({"_id": comment_id}, {"$set": data})


async def delete_comment(db, comment_id):
    return await db[COMMENTS_COLLECTION].delete_one({"_id": comment_id})


async def find_public_episode(db, episode_id, statuses):
    return await db[EPISODES_COLLECTION].find_one({
        "_id": episode_id,
        "status": {"$in": statuses},
    })


async def list_chapters(db, filters=None, limit=100):
    return await db[CHAPTERS_COLLECTION].find(filters or {}).sort("order", 1).to_list(length=limit)


async def find_chapter(db, filters):
    return await db[CHAPTERS_COLLECTION].find_one(filters)


async def increment_episode_view_count(db, episode_id, now):
    return await db[EPISODES_COLLECTION].find_one_and_update(
        {"_id": episode_id},
        {"$inc": {"view_count": 1}, "$set": {"updated_at": now}},
        return_document=True,
    )


async def upsert_episode_like(db, episode_id, user_id, now):
    return await db[LIKES_COLLECTION].update_one(
        {"episode_id": episode_id, "user_id": user_id},
        {"$setOnInsert": {
            "episode_id": episode_id,
            "user_id": user_id,
            "created_at": now,
        }},
        upsert=True,
    )


async def delete_episode_like(db, episode_id, user_id):
    return await db[LIKES_COLLECTION].delete_one({
        "episode_id": episode_id,
        "user_id": user_id,
    })


async def insert_comment(db, data):
    return await db[COMMENTS_COLLECTION].insert_one(data)


async def list_visible_episode_comments(db, episode_id, skip, limit):
    return await (
        db[COMMENTS_COLLECTION]
        .find({"episode_id": episode_id, "status": "visible"})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )


async def find_comment_for_episode(db, comment_id, episode_id):
    return await db[COMMENTS_COLLECTION].find_one({
        "_id": comment_id,
        "episode_id": episode_id,
    })


async def save_vlog_settings(db, value, updated_at):
    return await db[SETTINGS_COLLECTION].update_one(
        {"_id": VLOG_SETTINGS_KEY},
        {"$set": {"value": value, "updated_at": updated_at}},
        upsert=True,
    )


async def insert_media(db, data):
    return await db["vlog_media"].insert_one(data)


async def find_media_by_id(db, media_id):
    return await db["vlog_media"].find_one({"_id": media_id})


async def list_media(db, filters, skip, limit):
    return await db["vlog_media"].find(filters).sort("_id", -1).skip(skip).limit(limit).to_list(length=limit)


async def insert_chapter(db, data):
    return await db[CHAPTERS_COLLECTION].insert_one(data)


async def find_chapter_by_id(db, chapter_id):
    return await db[CHAPTERS_COLLECTION].find_one({"_id": chapter_id})


async def update_chapter(db, chapter_id, data):
    return await db[CHAPTERS_COLLECTION].update_one({"_id": chapter_id}, {"$set": data})


async def delete_chapter(db, chapter_id):
    return await db[CHAPTERS_COLLECTION].delete_one({"_id": chapter_id})


async def list_episode_ids_by_chapter(db, chapter_id, limit=100):
    return await db[EPISODES_COLLECTION].find({"chapter_id": chapter_id}, {"_id": 1}).to_list(length=limit)


async def delete_episodes_by_chapter(db, chapter_id):
    return await db[EPISODES_COLLECTION].delete_many({"chapter_id": chapter_id})


async def delete_likes_by_episode_ids(db, episode_ids):
    return await db[LIKES_COLLECTION].delete_many({"episode_id": {"$in": episode_ids}})


async def delete_comments_by_episode_ids(db, episode_ids):
    return await db[COMMENTS_COLLECTION].delete_many({"episode_id": {"$in": episode_ids}})


async def insert_episode(db, data):
    return await db[EPISODES_COLLECTION].insert_one(data)


async def find_episode_by_id(db, episode_id):
    return await db[EPISODES_COLLECTION].find_one({"_id": episode_id})


async def list_episodes_by_chapter(db, chapter_id, limit=50):
    return await db[EPISODES_COLLECTION].find({"chapter_id": chapter_id}).sort("order", 1).to_list(length=limit)


async def update_episode(db, episode_id, data):
    return await db[EPISODES_COLLECTION].update_one({"_id": episode_id}, {"$set": data})


async def delete_episode(db, episode_id):
    return await db[EPISODES_COLLECTION].delete_one({"_id": episode_id})


async def delete_likes_by_episode(db, episode_id):
    return await db[LIKES_COLLECTION].delete_many({"episode_id": episode_id})


async def delete_comments_by_episode(db, episode_id):
    return await db[COMMENTS_COLLECTION].delete_many({"episode_id": episode_id})
