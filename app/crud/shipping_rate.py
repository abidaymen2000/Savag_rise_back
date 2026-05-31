from datetime import datetime
import re
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder


COLLECTION = "shipping_rates"


def _normalize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc


def _norm_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _oid(rate_id: str) -> ObjectId:
    try:
        return ObjectId(rate_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de tarif de livraison invalide"
        )


async def create_shipping_rate(db, data: Any) -> Dict[str, Any]:
    now = datetime.utcnow()
    doc = jsonable_encoder(data)
    doc["country"] = doc["country"].strip()
    doc["city"] = _norm_text(doc.get("city"))
    doc["created_at"] = now
    doc["updated_at"] = now
    res = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": res.inserted_id})
    return _normalize(created)


async def list_shipping_rates(
    db,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    filters: Dict[str, Any] = {}
    if is_active is not None:
        filters["is_active"] = is_active

    cursor = (
        db[COLLECTION]
        .find(filters)
        .sort([("country", 1), ("city", 1), ("name", 1)])
        .skip(skip)
        .limit(limit)
    )
    return [_normalize(doc) async for doc in cursor]


async def get_shipping_rate(db, rate_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLLECTION].find_one({"_id": _oid(rate_id)})
    return _normalize(doc)


async def update_shipping_rate(db, rate_id: str, data: Any) -> Optional[Dict[str, Any]]:
    update_data = data.model_dump(exclude_unset=True)
    if "country" in update_data and update_data["country"] is not None:
        update_data["country"] = update_data["country"].strip()
    if "city" in update_data:
        update_data["city"] = _norm_text(update_data.get("city"))

    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db[COLLECTION].update_one(
            {"_id": _oid(rate_id)},
            {"$set": update_data}
        )
    return await get_shipping_rate(db, rate_id)


async def delete_shipping_rate(db, rate_id: str) -> bool:
    res = await db[COLLECTION].delete_one({"_id": _oid(rate_id)})
    return res.deleted_count == 1


async def resolve_shipping_rate(
    db,
    *,
    country: str,
    city: str,
    order_total: float,
) -> Dict[str, Any]:
    country_norm = country.strip()
    city_norm = city.strip()

    city_match = await db[COLLECTION].find_one({
        "is_active": True,
        "country": {"$regex": f"^{re.escape(country_norm)}$", "$options": "i"},
        "city": {"$regex": f"^{re.escape(city_norm)}$", "$options": "i"},
    })

    rate = city_match
    if not rate:
        rate = await db[COLLECTION].find_one({
            "is_active": True,
            "country": {"$regex": f"^{re.escape(country_norm)}$", "$options": "i"},
            "$or": [{"city": None}, {"city": ""}, {"city": {"$exists": False}}],
        })

    if not rate:
        rate = await db[COLLECTION].find_one({
            "is_active": True,
            "$or": [{"city": None}, {"city": ""}, {"city": {"$exists": False}}],
        })

    if not rate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun tarif de livraison actif pour cette adresse."
        )

    threshold = rate.get("free_shipping_threshold")
    amount = 0.0 if threshold is not None and order_total >= threshold else float(rate["price"])

    return {
        "shipping_rate_id": str(rate["_id"]),
        "shipping_rate_name": rate["name"],
        "shipping_amount": amount,
        "free_shipping_threshold": threshold,
    }
