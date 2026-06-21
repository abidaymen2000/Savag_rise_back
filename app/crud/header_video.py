SETTINGS_COLLECTION = "cms_settings"
HEADER_VIDEO_KEY = "store_header_video"


async def find_header_video_doc(db):
    return await db[SETTINGS_COLLECTION].find_one({"_id": HEADER_VIDEO_KEY})


async def save_header_video_config(db, value):
    await db[SETTINGS_COLLECTION].update_one(
        {"_id": HEADER_VIDEO_KEY},
        {"$set": {"value": value}},
        upsert=True,
    )


async def delete_header_video_config_for_file(db, file_id):
    return await db[SETTINGS_COLLECTION].delete_one(
        {"_id": HEADER_VIDEO_KEY, "value.video.file_id": file_id}
    )


async def unset_header_image_for_file(db, file_id):
    return await db[SETTINGS_COLLECTION].update_one(
        {"_id": HEADER_VIDEO_KEY, "value.image.file_id": file_id},
        {"$unset": {"value.image": ""}},
    )
