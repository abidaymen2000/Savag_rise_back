from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, status

from app.schemas.pack import PackComponentOut, PackOut, PackProductSummary


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


def normalize_pack_components(data: Dict) -> Dict:
    components = data.get("components")
    if not components:
        components = [{"product_id": product_id, "qty": 1} for product_id in data.get("product_ids", [])]
    normalized = []
    for component in components:
        item = dict(component)
        item["id"] = item.get("id") or str(uuid4())
        item["qty"] = int(item.get("qty", 1) or 1)
        normalized.append(item)
    data["components"] = normalized
    data["product_ids"] = [component["product_id"] for component in normalized]
    return data


def _find_variant(product: Dict, color: Optional[str]) -> Optional[Dict]:
    if not color:
        return None
    for variant in product.get("variants", []):
        if variant.get("color") == color:
            return variant
    return None


def _variant_has_size(variant: Dict, size: Optional[str]) -> bool:
    if not size:
        return True
    return any(row.get("size") == size for row in variant.get("sizes", []))


async def validate_pack_components(db, components: List[Dict]) -> None:
    if len(components) < 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un pack doit contenir au minimum deux composants")
    for component in components:
        product = await db["products"].find_one({"_id": validate_object_id(component["product_id"], "Produit ID")})
        if not product:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Un ou plusieurs produits du pack sont introuvables")
        if component.get("color"):
            variant = _find_variant(product, component["color"])
            if not variant:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Une couleur configuree dans le pack est introuvable")
            if not _variant_has_size(variant, component.get("size")):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Une taille configuree dans le pack est introuvable")


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
    components = payload.get("components") or [{"id": str(index), "product_id": product_id, "qty": 1} for index, product_id in enumerate(payload.get("product_ids", []), start=1)]
    component_out = []
    products = []
    original_price = 0.0
    for component in components:
        product = await product_summary(db, component["product_id"])
        products.append(product)
        qty = int(component.get("qty", 1) or 1)
        original_price += product.price * qty
        component_out.append(PackComponentOut(
            id=component["id"],
            product_id=component["product_id"],
            color=component.get("color"),
            size=component.get("size"),
            qty=qty,
            product=product,
            locked_variant=bool(component.get("color") or component.get("size")),
        ))
    original_price = round(original_price, 2)
    pack_price, savings = compute_pack_prices(
        original_price,
        payload.get("discount_type", "percent"),
        payload.get("discount_value", 0),
    )
    payload["products"] = products
    payload["components"] = component_out
    payload["product_ids"] = [component.product_id for component in component_out]
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

        components = pack.get("components") or [{"id": str(index), "product_id": product_id, "qty": 1} for index, product_id in enumerate(pack.get("product_ids", []), start=1)]
        components_by_id = {component["id"]: component for component in components}
        if len(selection.items) != len(components):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Les composants selectionnes ne correspondent pas au pack")

        pack_original = 0.0
        component_payloads = []
        for item in selection.items:
            component = components_by_id.get(item.component_id) if item.component_id else None
            if component is None:
                matches = [candidate for candidate in components if candidate["product_id"] == item.product_id]
                if len(matches) != 1:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "component_id requis pour ce pack")
                component = matches[0]
            if item.product_id != component["product_id"]:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Produit invalide pour ce composant du pack")
            if component.get("color") and item.color != component["color"]:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Couleur invalide pour ce composant du pack")
            if component.get("size") and item.size != component["size"]:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Taille invalide pour ce composant du pack")

            component_qty = int(component.get("qty", 1) or 1)
            line_qty = component_qty * item.qty * selection.qty
            line_total = line_qty * item.unit_price
            pack_original += line_total
            expanded_items.append({
                "product_id": item.product_id,
                "color": item.color,
                "size": item.size,
                "qty": line_qty,
                "unit_price": item.unit_price,
                "pack_id": str(pack["_id"]),
                "pack_component_id": component["id"],
            })
            component_payloads.append({
                "component_id": component["id"],
                "product_id": item.product_id,
                "color": item.color,
                "size": item.size,
                "qty": component_qty * item.qty,
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
