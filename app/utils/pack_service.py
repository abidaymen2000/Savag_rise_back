from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.schemas.pack import PackOut, PackProductSummary


PACKS_COLLECTION = "packs"
PUBLIC_PACK_STATUSES = ["active"]


def now_utc() -> datetime:
    return datetime.utcnow()


def validate_object_id(value: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} invalide")


def first_product_image(product: Dict) -> Optional[str]:
    for variant in product.get("variants", []):
        for image in variant.get("images", []):
            if isinstance(image, dict) and image.get("url"):
                return image["url"]
            if isinstance(image, str):
                return image
    return None


async def product_summary(db, product_id: str) -> PackProductSummary:
    product = await db["products"].find_one({"_id": validate_object_id(product_id, "Produit ID")})
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit introuvable")
    return PackProductSummary(
        id=str(product["_id"]),
        name=product["name"],
        full_name=product.get("full_name"),
        price=float(product["price"]),
        image_url=first_product_image(product),
        in_stock=product.get("in_stock", True),
    )


def compute_pack_prices(original_price: float, discount_type: str, discount_value: float) -> tuple[float, float]:
    original_price = round(float(original_price), 2)
    if discount_type == "percent":
        savings = original_price * (float(discount_value) / 100)
    else:
        savings = float(discount_value)
    savings = round(min(max(savings, 0), original_price), 2)
    return round(original_price - savings, 2), savings


def is_pack_public(doc: Dict) -> bool:
    if doc.get("status") not in PUBLIC_PACK_STATUSES:
        return False
    now = now_utc()
    if doc.get("starts_at") and doc["starts_at"] > now:
        return False
    if doc.get("ends_at") and doc["ends_at"] < now:
        return False
    return True


async def pack_out(db, doc: Dict) -> PackOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    products = [await product_summary(db, product_id) for product_id in payload.get("product_ids", [])]
    original_price = round(sum(product.price for product in products), 2)
    pack_price, savings = compute_pack_prices(
        original_price,
        payload.get("discount_type", "percent"),
        payload.get("discount_value", 0),
    )
    payload["products"] = products
    payload["original_price"] = original_price
    payload["pack_price"] = pack_price
    payload["savings_value"] = savings
    return PackOut(**payload)


async def validate_pack_products_exist(db, product_ids: List[str]) -> None:
    if len(product_ids) < 2 or len(set(product_ids)) != len(product_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un pack doit contenir au minimum deux produits differents")
    object_ids = [validate_object_id(product_id, "Produit ID") for product_id in product_ids]
    count = await db["products"].count_documents({"_id": {"$in": object_ids}})
    if count != len(product_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Un ou plusieurs produits du pack sont introuvables")


async def calculate_order_packs(db, selections) -> Dict:
    expanded_items = []
    pack_items = []
    original_subtotal = 0.0
    discount_total = 0.0

    for selection in selections or []:
        pack_oid = validate_object_id(selection.pack_id, "Pack ID")
        pack = await db[PACKS_COLLECTION].find_one({"_id": pack_oid})
        if not pack or not is_pack_public(pack):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pack indisponible")

        expected_product_ids = set(pack.get("product_ids", []))
        selected_product_ids = {item.product_id for item in selection.items}
        if selected_product_ids != expected_product_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Les produits selectionnes ne correspondent pas au pack")

        pack_original = 0.0
        component_payloads = []
        for item in selection.items:
            line_qty = item.qty * selection.qty
            line_total = line_qty * item.unit_price
            pack_original += line_total
            expanded_items.append({
                "product_id": item.product_id,
                "color": item.color,
                "size": item.size,
                "qty": line_qty,
                "unit_price": item.unit_price,
                "pack_id": str(pack["_id"]),
            })
            component_payloads.append({
                "product_id": item.product_id,
                "color": item.color,
                "size": item.size,
                "qty": item.qty,
                "unit_price": item.unit_price,
            })

        if pack.get("discount_type") == "percent":
            pack_discount = pack_original * (float(pack.get("discount_value", 0)) / 100)
        else:
            pack_discount = float(pack.get("discount_value", 0)) * selection.qty
        pack_discount = round(min(max(pack_discount, 0), pack_original), 2)
        pack_final = round(pack_original - pack_discount, 2)

        original_subtotal += pack_original
        discount_total += pack_discount
        pack_items.append({
            "pack_id": str(pack["_id"]),
            "title": pack["title"],
            "qty": selection.qty,
            "items": component_payloads,
            "original_amount": round(pack_original, 2),
            "discount_value": pack_discount,
            "final_amount": pack_final,
        })

    return {
        "expanded_items": expanded_items,
        "pack_items": pack_items,
        "original_subtotal": round(original_subtotal, 2),
        "discount_value": round(discount_total, 2),
    }
