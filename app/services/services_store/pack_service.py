from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import pack as pack_crud
from app.core.pagination import build_page
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
    product = await pack_crud.find_product_by_id(db, validate_object_id(product_id, "Produit ID"))
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
        product = await pack_crud.find_product_by_id(db, validate_object_id(component["product_id"], "Produit ID"))
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
    count = await pack_crud.count_products_by_ids(db, object_ids)
    if count != len(product_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Un ou plusieurs produits du pack sont introuvables")


async def list_public_packs(db, skip: int, limit: int) -> list[PackOut]:
    docs = await pack_crud.list_packs(db, {"status": "active"}, skip, limit)
    return [await pack_out(db, doc) for doc in docs if is_pack_public(doc)]


async def get_public_pack(db, pack_id: str) -> PackOut:
    doc = await pack_crud.find_pack_by_id(db, validate_object_id(pack_id, "Pack ID"))
    if not doc or not is_pack_public(doc):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
    return await pack_out(db, doc)


async def admin_list_packs(db, status_filter, skip: int, limit: int) -> list[PackOut]:
    filters = {}
    if status_filter:
        filters["status"] = status_filter
    docs = await pack_crud.list_packs(db, filters, skip, limit)
    return [await pack_out(db, doc) for doc in docs]


async def admin_list_packs_page(db, pagination, status_filter):
    filters = {}
    if status_filter:
        filters["status"] = status_filter
    total = await pack_crud.count_packs(db, filters)
    docs = await pack_crud.list_packs(db, filters, pagination.skip, pagination.page_size)
    return build_page(
        items=[await pack_out(db, doc) for doc in docs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        sort={"by": "order", "dir": "asc"},
        filters={"status": status_filter},
    )


async def admin_create_pack(db, payload) -> PackOut:
    now = now_utc()
    data = normalize_pack_components(payload.model_dump())
    await validate_pack_components(db, data["components"])
    data["created_at"] = now
    data["updated_at"] = now
    res = await pack_crud.insert_pack(db, data)
    created = await pack_crud.find_pack_by_id(db, res.inserted_id)
    return await pack_out(db, created)


async def admin_get_pack(db, pack_id: str) -> PackOut:
    doc = await pack_crud.find_pack_by_id(db, validate_object_id(pack_id, "Pack ID"))
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
    return await pack_out(db, doc)


async def admin_update_pack(db, pack_id: str, payload) -> PackOut:
    oid = validate_object_id(pack_id, "Pack ID")
    existing = await pack_crud.find_pack_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
    data = payload.model_dump(exclude_unset=True)
    if "components" in data or "product_ids" in data:
        base = {k: v for k, v in existing.items() if k != "_id"}
        base.update(data)
        base = normalize_pack_components(base)
        await validate_pack_components(db, base["components"])
        data["components"] = base["components"]
        data["product_ids"] = base["product_ids"]
    data["updated_at"] = now_utc()
    await pack_crud.update_pack(db, oid, data)
    updated = await pack_crud.find_pack_by_id(db, oid)
    return await pack_out(db, updated)


async def admin_delete_pack(db, pack_id: str) -> None:
    oid = validate_object_id(pack_id, "Pack ID")
    existing = await pack_crud.find_pack_by_id(db, oid)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pack introuvable")
    await pack_crud.delete_pack(db, oid)


async def calculate_order_packs(db, selections) -> Dict:
    expanded_items = []
    pack_items = []
    original_subtotal = 0.0
    discount_total = 0.0

    for selection in selections or []:
        pack_oid = validate_object_id(selection.pack_id, "Pack ID")
        pack = await pack_crud.find_pack_by_id(db, pack_oid)
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
