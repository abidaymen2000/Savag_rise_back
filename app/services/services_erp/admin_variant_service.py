from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from app.crud import variant as variant_crud
from app.services.services_cms.imagekit_upload import upload_to_imagekit


def parse_oid(product_id: str) -> str:
    try:
        ObjectId(product_id)
        return product_id
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID produit invalide")


async def create_variant(db, product_id: str, variant):
    return await variant_crud.add_variant(db, parse_oid(product_id), variant.model_dump())


async def update_stock(db, product_id: str, color: str, size: str, new_stock: int):
    modified = await variant_crud.update_variant_stock(db, parse_oid(product_id), color, size, new_stock)
    if not modified:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante ou taille non trouvee")


async def upload_variant_image(db, product_id: str, color: str, file: UploadFile):
    url = await upload_to_imagekit(file)
    return await variant_crud.add_image_to_variant(db, parse_oid(product_id), color, {"url": url})


async def delete_variant_image(db, product_id: str, color: str, image_id: str):
    success = await variant_crud.remove_image_from_variant(db, parse_oid(product_id), color, image_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image non trouvee")
