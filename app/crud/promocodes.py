# app/crud/promocodes.py
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import ReturnDocument

from app.models.promocode import promocode_doc
from app.schemas.promocode import PromoCreate, PromoUpdate

COLL = "promocodes"


def oid_str(obj) -> str:
    return str(obj["_id"])


def _norm(code: str) -> str:
    return code.upper().strip()

def _aware(dt):
    if dt is None: 
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

async def create_promocode(db, data: PromoCreate) -> Dict[str, Any]:
    d = promocode_doc(**data.model_dump())
    d["code"] = _norm(d["code"])  # ⇠ normalisation ICI
    d["starts_at"] = _aware(d.get("starts_at"))
    d["ends_at"]   = _aware(d.get("ends_at"))
    d["created_at"] = datetime.now(timezone.utc)
    d["updated_at"] = d["created_at"]
    res = await db[COLL].insert_one(d)
    d["_id"] = res.inserted_id
    d["id"] = str(d["_id"])
    return d


async def get_by_code(db, code: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLL].find_one({"code": _norm(code)})
    if doc:
        doc["id"] = str(doc["_id"])
    return doc


async def get_by_id(db, promo_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLL].find_one({"_id": ObjectId(promo_id)})
    if doc:
        doc["id"] = str(doc["_id"])
    return doc


async def list_promocodes(db, skip=0, limit=50, q: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if q:
        query = {
            "$or": [
                {"code": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
            ]
        }
    cur = db[COLL].find(query).skip(skip).limit(limit).sort("created_at", -1)
    items: List[Dict[str, Any]] = []
    async for doc in cur:
        doc["id"] = str(doc["_id"])
        items.append(doc)
    return items


async def update_promocode(db, promo_id: str, data: PromoUpdate) -> Optional[Dict[str, Any]]:
    upd = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if "code" in upd:
        upd["code"] = _norm(upd["code"])
    if "starts_at" in upd:
        upd["starts_at"] = _aware(upd["starts_at"])
    if "ends_at" in upd:
        upd["ends_at"] = _aware(upd["ends_at"])
    upd["updated_at"] = datetime.now(timezone.utc)

    res = await db[COLL].find_one_and_update(
        {"_id": ObjectId(promo_id)},
        {"$set": upd},
        return_document=ReturnDocument.AFTER,  # ⇠ ici
    )
    if res:
        res["id"] = str(res["_id"])
    return res


async def delete_promocode(db, promo_id: str) -> bool:
    res = await db[COLL].delete_one({"_id": ObjectId(promo_id)})
    return res.deleted_count == 1


# --- Ancienne incrémentation (au paiement). Conservée si tu en as besoin ailleurs,
# mais dans le flux recommandé on utilise reserve_use()/release_use().
async def increment_use(db, code: str, user_id: Optional[str]):
    now = datetime.now(timezone.utc)
    update = {"$inc": {"uses_count": 1}, "$set": {"updated_at": now}}
    if user_id:
        update["$inc"][f"user_uses.{user_id}"] = 1
    await db[COLL].update_one({"code": _norm(code)}, update)


async def reserve_use(db, code: str, user_id: str):
    """
    Réserve un usage pour (code, user_id) de façon atomique.
    Echec si : code inactif/expiré, max_uses atteint, ou limite par user atteinte.
    Renvoie le document après mise à jour si succès, sinon None.
    """
    now = datetime.now(timezone.utc)
    ncode = _norm(code)

    query = {
        "code": ncode,
        "is_active": True,
        "$and": [
            # fenêtres temporelles
            {"$or": [{"starts_at": {"$exists": False}}, {"starts_at": None}, {"starts_at": {"$lte": now}}]},
            {"$or": [{"ends_at": {"$exists": False}}, {"ends_at": None}, {"ends_at": {"$gte": now}}]},
            {
                "$expr": {
                    "$and": [
                        # max_uses non défini OU uses_count (0 par défaut) < max_uses
                        {"$or": [
                            {"$eq": ["$max_uses", None]},
                            {"$lt": [
                                {"$ifNull": ["$uses_count", 0]},
                                "$max_uses"
                            ]}
                        ]},
                        # per_user_limit non défini OU user_uses[user_id] (0 par défaut) < per_user_limit
                        {"$or": [
                            {"$eq": ["$per_user_limit", None]},
                            {"$lt": [
                                {"$ifNull": [f"$user_uses.{user_id}", 0]},
                                "$per_user_limit"
                            ]}
                        ]},
                    ]
                }
            }
        ]
    }

    update = {
        "$inc": {
            "uses_count": 1,
            f"user_uses.{user_id}": 1
        },
        "$set": {"updated_at": now}
    }

    return await db[COLL].find_one_and_update(
        query,
        update,
        return_document=ReturnDocument.AFTER
    )


async def release_use(db, code: str, user_id: str):
    """
    Libère une réservation précédemment faite (commande annulée, etc.).
    Ne descend jamais en négatif grâce au filtre.
    """
    now = datetime.now(timezone.utc)
    ncode = _norm(code)
    query = {
        "code": ncode,
        "uses_count": {"$gt": 0},
        f"user_uses.{user_id}": {"$gt": 0}
    }
    update = {
        "$inc": {
            "uses_count": -1,
            f"user_uses.{user_id}": -1
        },
        "$set": {"updated_at": now}
    }
    await db[COLL].update_one(query, update)
