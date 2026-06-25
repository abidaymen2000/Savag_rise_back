from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from app.crud import product as product_crud
from app.crud import variant as variant_crud
from app.domain.inventory import inventory_projection
from app.schemas.variant import VariantInventoryOut
from app.services.services_cms.imagekit_upload import upload_to_imagekit
from app.services.services_erp.audit_service import log_action
from app.services.services_store.product_service import product_to_out


def parse_oid(product_id: str) -> str:
    try:
        ObjectId(product_id)
        return product_id
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID produit invalide")


async def create_variant(db, product_id: str, variant):
    product_id = parse_oid(product_id)
    payload = variant.model_dump()
    payload["sizes"] = [
        {
            "size": row["size"],
            "stock_on_hand": int(row.get("stock_on_hand", 0) or 0),
            "stock_reserved": int(row.get("stock_reserved", 0) or 0),
        }
        for row in payload.get("sizes", [])
    ]
    created_variant = await variant_crud.add_variant(db, product_id, payload)
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")

    created_color = str(created_variant.get("color", "")).strip().casefold()
    for mapped_variant in product_to_out(product).variants:
        if mapped_variant.color.strip().casefold() == created_color:
            return mapped_variant
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Variante creee mais introuvable")


def _find_variant(variants, color: str):
    normalized_color = color.strip().casefold()
    return next(
        (variant for variant in variants if str(variant.get("color", "")).strip().casefold() == normalized_color),
        None,
    )


async def rename_color(db, product_id: str, current_color: str, payload, admin):
    product_id = parse_oid(product_id)
    new_color = payload.color.strip()
    if not new_color:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La couleur est obligatoire")
    variants = await variant_crud.find_variants(db, product_id)
    if variants is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")
    current_variant = _find_variant(variants, current_color)
    if not current_variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Couleur introuvable")

    current_stored_color = current_variant["color"]
    duplicate = _find_variant(variants, new_color)
    if duplicate and duplicate is not current_variant:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette couleur existe deja pour ce produit")

    if current_stored_color != new_color:
        modified = await variant_crud.rename_variant_color(db, product_id, current_stored_color, new_color)
        if not modified:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La couleur n'a pas pu etre renommee")

    result = {**current_variant, "color": new_color, "sizes": [inventory_projection(dict(row)) for row in current_variant.get("sizes", [])]}
    await log_action(
        db,
        admin=admin,
        action="variant.color.rename",
        module="inventory",
        entity_type="product",
        entity_id=product_id,
        metadata={"from": current_stored_color, "to": new_color},
    )
    return VariantInventoryOut(**result)


async def add_size(db, product_id: str, color: str, payload, admin):
    product_id = parse_oid(product_id)
    size = payload.size.strip()
    if not size:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La taille est obligatoire")
    variants = await variant_crud.find_variants(db, product_id)
    if variants is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")
    variant = _find_variant(variants, color)
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Couleur introuvable")

    if any(str(item.get("size", "")).strip().casefold() == size.casefold() for item in variant.get("sizes", [])):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette taille existe deja pour cette couleur")

    size_data = {"size": size, "stock_on_hand": payload.stock_on_hand, "stock_reserved": 0}
    modified = await variant_crud.add_size_to_variant(db, product_id, variant["color"], size_data)
    if not modified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La taille n'a pas pu etre ajoutee")

    result = {**variant, "sizes": [inventory_projection(dict(row)) for row in [*variant.get("sizes", []), size_data]]}
    await log_action(
        db,
        admin=admin,
        action="variant.size.add",
        module="inventory",
        entity_type="product",
        entity_id=product_id,
        metadata={"color": variant["color"], "size": size, "stock_on_hand": payload.stock_on_hand},
    )
    return VariantInventoryOut(**result)


async def update_stock(db, product_id: str, color: str, size: str, new_stock_on_hand: int):
    modified = await variant_crud.update_variant_stock(db, parse_oid(product_id), color, size, new_stock_on_hand)
    if not modified:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante ou taille non trouvee")


async def upload_variant_image(db, product_id: str, color: str, file: UploadFile):
    url = await upload_to_imagekit(file)
    return await variant_crud.add_image_to_variant(db, parse_oid(product_id), color, {"url": url})


async def delete_variant_image(db, product_id: str, color: str, image_id: str):
    success = await variant_crud.remove_image_from_variant(db, parse_oid(product_id), color, image_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image non trouvee")
