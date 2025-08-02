from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder

# --------------------
# CRUD Produits
# --------------------

async def get_product(db, product_id: str) -> Optional[Dict[str, Any]]:
    return await db["products"].find_one({"_id": ObjectId(product_id)})

async def get_products(db, skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    cursor = db["products"].find().skip(skip).limit(limit)
    return await cursor.to_list(length=limit)

async def create_product(db, product: Any) -> Dict[str, Any]:
    doc = jsonable_encoder(product)
    res = await db["products"].insert_one(doc)
    return await get_product(db, str(res.inserted_id))

async def update_product(db, product_id: str, data: Any) -> Optional[Dict[str, Any]]:
    oid = ObjectId(product_id)
    upd = data.dict(exclude_unset=True)
    if upd:
        await db["products"].update_one({"_id": oid}, {"$set": upd})
    return await get_product(db, product_id)

async def delete_product(db, product_id: str) -> None:
    await db["products"].delete_one({"_id": ObjectId(product_id)})


# --------------------
# Recherche & filtres
# --------------------

async def search_products(
    db,
    text: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    style: Optional[str] = None,
    season: Optional[str] = None,
    target_audience: Optional[str] = None,
    color: Optional[str] = None,
    size: Optional[str] = None,
    sort_by: str = "price",
    sort_dir: int = 1,
    skip: int = 0,
    limit: int = 10
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}

    # Plein-texte
    if text:
        query["$text"] = {"$search": text}

    # Filtre prix
    if min_price is not None or max_price is not None:
        price_f: Dict[str, Any] = {}
        if min_price is not None:
            price_f["$gte"] = min_price
        if max_price is not None:
            price_f["$lte"] = max_price
        query["price"] = price_f

    # Facettes standard
    for field, val in (("style", style), ("season", season), ("target_audience", target_audience)):
        if val:
            query[field] = val

    # Filtre sur les variants embarqués (toujours OK, même si la logique CRUD est déportée)
    if color or size:
        elem: Dict[str, Any] = {}
        if color:
            elem["color"] = {"$regex": f"^{color}$", "$options": "i"}
        if size:
            elem["size"] = {"$regex": f"^{size}$", "$options": "i"}
        query["variants"] = {"$elemMatch": elem}

    # Curseur et tri
    cursor = db["products"].find(query)
    if text:
        cursor = cursor.sort([("score", {"$meta": "textScore"})])
    else:
        cursor = cursor.sort(sort_by, sort_dir)

    docs = await cursor.skip(skip).limit(limit).to_list(length=limit)
    for d in docs:
        d["id"] = str(d["_id"])
    return docs


# --------------------
# (Optionnel) Catégories
# --------------------

async def add_category_to_product(db, product_id: str, category_name: str) -> Optional[Dict[str, Any]]:
    oid = ObjectId(product_id)
    await db["products"].update_one(
        {"_id": oid},
        {"$addToSet": {"categories": category_name}}
    )
    return await get_product(db, product_id)
