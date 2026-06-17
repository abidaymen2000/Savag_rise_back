import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from app.db import client
from app.models.admin import AdminInDB
from app.config import settings

COL = client[settings.MONGODB_DB_NAME]["admins"]
PAGES_COL = client[settings.MONGODB_DB_NAME]["cms_pages"]

DEFAULT_CMS_PAGES = [
    {"key": "dashboard", "label": "Dashboard", "section": "ACCUEIL", "path": "/admin", "icon": "layout-grid", "order": 10, "is_active": True, "requires_permission": False},
    {"key": "orders", "label": "Commandes", "section": "VENTES", "path": "/admin/orders", "icon": "shopping-cart", "order": 100, "is_active": True, "requires_permission": True},
    {"key": "shipping", "label": "Livraison", "section": "VENTES", "path": "/admin/shipping", "icon": "truck", "order": 110, "is_active": True, "requires_permission": True},
    {"key": "promocodes", "label": "Codes promo", "section": "VENTES", "path": "/admin/promocodes", "icon": "percent", "order": 120, "is_active": True, "requires_permission": True},
    {"key": "loyalty", "label": "Fidelite", "section": "VENTES", "path": "/admin/loyalty", "icon": "gift", "order": 130, "is_active": True, "requires_permission": True},
    {"key": "products", "label": "Produits", "section": "CATALOGUE", "path": "/admin/products", "icon": "package", "order": 200, "is_active": True, "requires_permission": True},
    {"key": "packs", "label": "Packs", "section": "CATALOGUE", "path": "/admin/packs", "icon": "boxes", "order": 210, "is_active": True, "requires_permission": True},
    {"key": "categories", "label": "Categories", "section": "CATALOGUE", "path": "/admin/categories", "icon": "tags", "order": 220, "is_active": True, "requires_permission": True},
    {"key": "header_video", "label": "Video hero", "section": "CONTENU", "path": "/admin/header-video", "icon": "video", "order": 300, "is_active": True, "requires_permission": True},
    {"key": "vlog", "label": "Vlog", "section": "CONTENU", "path": "/admin/vlog", "icon": "clapperboard", "order": 310, "is_active": True, "requires_permission": True},
    {"key": "engagement", "label": "Engagement", "section": "CONTENU", "path": "/admin/engagement", "icon": "message-square", "order": 320, "is_active": True, "requires_permission": True},
    {"key": "users", "label": "Clients", "section": "CLIENTS", "path": "/admin/users", "icon": "users", "order": 400, "is_active": True, "requires_permission": True},
    {"key": "admins", "label": "Admins", "section": "SYSTEME", "path": "/admin/admins", "icon": "shield", "order": 500, "is_active": True, "requires_permission": True},
]

def _norm_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def _to_object_id(value: str) -> Optional[ObjectId]:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None

async def get_by_email(email: str) -> Optional[AdminInDB]:
    data = await COL.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
    data = _norm_id(data)
    return AdminInDB(**data) if data else None


async def get_by_id(admin_id: str) -> Optional[AdminInDB]:
    oid = _to_object_id(admin_id)
    if not oid:
        return None
    data = await COL.find_one({"_id": oid})
    data = _norm_id(data)
    return AdminInDB(**data) if data else None


async def list_admins(filters: Dict[str, Any], skip: int, limit: int) -> List[AdminInDB]:
    docs = await COL.find(filters).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return [AdminInDB(**_norm_id(doc)) for doc in docs]


async def count_admins(filters: Dict[str, Any]) -> int:
    return await COL.count_documents(filters)

async def create(admin: AdminInDB) -> AdminInDB:
    admin.updated_at = datetime.utcnow()
    payload = admin.model_dump(by_alias=True, exclude_none=True)
    payload.pop("_id", None)
    res = await COL.insert_one(payload)
    admin.id = str(res.inserted_id)
    return admin


async def update_admin(admin_id: str, data: Dict[str, Any]) -> Optional[AdminInDB]:
    if not data:
        return await get_by_id(admin_id)
    oid = _to_object_id(admin_id)
    if not oid:
        return None
    data["updated_at"] = datetime.utcnow()
    await COL.update_one({"_id": oid}, {"$set": data})
    return await get_by_id(admin_id)


async def delete_admin(admin_id: str) -> bool:
    oid = _to_object_id(admin_id)
    if not oid:
        return False
    res = await COL.delete_one({"_id": oid})
    return res.deleted_count == 1

async def update_password_hash(email: str, password_hash: str) -> bool:
    res = await COL.update_one(
        {"email": email},
        {"$set": {"password_hash": password_hash, "updated_at": datetime.utcnow()}}
    )
    return res.modified_count == 1


def _page_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc


async def ensure_default_cms_pages() -> None:
    now = datetime.utcnow()
    for page in DEFAULT_CMS_PAGES:
        await PAGES_COL.update_one(
            {"key": page["key"]},
            {
                "$setOnInsert": {**page, "created_at": now},
                "$set": {"updated_at": now},
            },
            upsert=True,
        )
        await PAGES_COL.update_one(
            {"key": page["key"], "$or": [{"icon": {"$exists": False}}, {"icon": None}, {"icon": ""}]},
            {"$set": {"icon": page["icon"], "updated_at": now}},
        )
    await PAGES_COL.update_one(
        {"key": "dashboard", "icon": "layout-dashboard"},
        {"$set": {"icon": "layout-grid", "updated_at": now}},
    )


async def list_cms_pages(include_inactive: bool = False) -> List[Dict[str, Any]]:
    filters = {} if include_inactive else {"is_active": True}
    docs = await PAGES_COL.find(filters).sort("order", 1).to_list(length=200)
    return [_page_out(doc) for doc in docs]


async def get_cms_page_by_key(key: str) -> Optional[Dict[str, Any]]:
    data = await PAGES_COL.find_one({"key": key})
    return _page_out(data) if data else None


async def get_permission_keys() -> List[str]:
    docs = await PAGES_COL.find(
        {"is_active": True, "requires_permission": True},
        {"key": 1},
    ).to_list(length=200)
    return [doc["key"] for doc in docs]


async def get_cms_page(page_id: str) -> Optional[Dict[str, Any]]:
    oid = _to_object_id(page_id)
    if not oid:
        return None
    data = await PAGES_COL.find_one({"_id": oid})
    return _page_out(data) if data else None


async def create_cms_page(data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    payload = {
        **data,
        "created_at": now,
        "updated_at": now,
    }
    res = await PAGES_COL.insert_one(payload)
    created = await PAGES_COL.find_one({"_id": res.inserted_id})
    return _page_out(created)


async def update_cms_page(page_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not data:
        return await get_cms_page(page_id)
    oid = _to_object_id(page_id)
    if not oid:
        return None
    data["updated_at"] = datetime.utcnow()
    await PAGES_COL.update_one({"_id": oid}, {"$set": data})
    return await get_cms_page(page_id)


async def delete_cms_page(page_id: str) -> bool:
    oid = _to_object_id(page_id)
    if not oid:
        return False
    page = await PAGES_COL.find_one({"_id": oid})
    if not page:
        return False
    res = await PAGES_COL.delete_one({"_id": oid})
    if res.deleted_count == 1:
        await COL.update_many({}, {"$pull": {"permissions": page["key"]}})
        return True
    return False
