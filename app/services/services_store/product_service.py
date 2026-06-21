from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import HTTPException, Request
from pymongo import ASCENDING, DESCENDING

from app.analytics.service import track_event
from app.core.pagination import build_page
from app.crud import product as product_crud
from app.schemas.product import ProductOut


def product_to_out(product: Dict[str, Any]) -> ProductOut:
    payload: Dict[str, Any] = {k: v for k, v in product.items() if k != "_id"}
    payload["id"] = str(product["_id"])

    remapped_variants = []
    for variant in payload.get("variants", []):
        variant_payload = dict(variant)
        remapped_images = []
        for image in variant_payload.get("images", []):
            if isinstance(image, dict):
                image_url = image.get("url")
                if not image_url:
                    continue
                image_id = image.get("_id", image.get("id"))
                remapped_images.append({
                    "id": str(image_id or image_url),
                    **{k: v for k, v in image.items() if k not in ("_id", "id")},
                })
            elif image:
                remapped_images.append({"id": str(image), "url": image})
        variant_payload["images"] = remapped_images
        remapped_variants.append(variant_payload)
    payload["variants"] = remapped_variants

    return ProductOut(**payload)


async def list_products(db, skip: int = 0, limit: int = 10) -> list[ProductOut]:
    return [product_to_out(product) for product in await product_crud.get_products(db, skip, limit)]


async def list_products_page(db, pagination, gender: Optional[str], in_stock: Optional[bool], q: Optional[str]):
    filters: Dict[str, Any] = {}
    if gender:
        filters["gender"] = gender
    if in_stock is not None:
        filters["in_stock"] = in_stock
    if q:
        filters["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"full_name": {"$regex": q, "$options": "i"}},
            {"sku": {"$regex": q, "$options": "i"}},
        ]

    total = await product_crud.count_products(db, filters)
    docs = await product_crud.list_products_page(db, filters, pagination.skip, pagination.page_size)
    return build_page(
        items=[product_to_out(doc) for doc in docs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "_id", "dir": "desc"},
        filters={"gender": gender, "in_stock": in_stock, "q": q},
    )


async def search_products(
    db,
    request: Request,
    current_user,
    text: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    gender: Optional[str],
    color: Optional[str],
    size: Optional[str],
    skip: int,
    limit: int,
    sort: Optional[str],
) -> list[ProductOut]:
    if text:
        await track_event(
            db,
            "search_submitted",
            user_id=str(current_user["_id"]) if current_user else None,
            metadata={"query": text, "filters": {"gender": gender, "color": color, "size": size}},
            request=request,
        )

    pipeline = []
    filters: dict = {}
    if text:
        filters["$text"] = {"$search": text}
    if min_price is not None or max_price is not None:
        price_filter: dict = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        filters["price"] = price_filter
    if gender:
        filters["gender"] = gender
    if color or size:
        variant_filter: dict = {}
        if color:
            variant_filter["color"] = color
        if size:
            variant_filter["size"] = size
        filters["variants"] = {"$elemMatch": variant_filter}
    if filters:
        pipeline.append({"$match": filters})
    if sort:
        field, direction = sort.split(":")
        dir_flag = ASCENDING if direction == "asc" else DESCENDING
        pipeline.append({"$sort": {field: dir_flag}})
    pipeline += [{"$skip": skip}, {"$limit": limit}]

    raw = await product_crud.aggregate_products(db, pipeline, limit)
    return [product_to_out(doc) for doc in raw]


async def get_product_detail(db, product_id: str, request: Request, current_user) -> ProductOut:
    try:
        ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalide")

    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouve")

    await track_event(
        db,
        "product_viewed",
        user_id=str(current_user["_id"]) if current_user else None,
        product_id=product_id,
        metadata={
            "product_name": product.get("full_name") or product.get("name"),
            "style_id": product.get("style_id"),
        },
        request=request,
    )
    return product_to_out(product)
