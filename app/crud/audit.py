from datetime import datetime


COLLECTION = "admin_audit_logs"


async def insert_audit_log(db, data):
    data["created_at"] = data.get("created_at") or datetime.utcnow()
    return await db[COLLECTION].insert_one(data)


async def list_audit_logs(db, filters, skip, limit):
    return await db[COLLECTION].find(filters).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)


async def count_audit_logs(db, filters):
    return await db[COLLECTION].count_documents(filters)
