# app/routers/variants.py

from typing import List
from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Path,
    UploadFile,
    File,
)
from ..db import get_db
from ..schemas.variant import VariantCreate, VariantOut
from ..schemas.image import ImageOut
from ..crud.variant import (
    add_variant,
    get_variants,
    update_variant_stock,
    add_image_to_variant,
    remove_image_from_variant,
)
from ..utils.imagekit_upload import upload_to_imagekit

router = APIRouter(
    prefix="/products/{product_id}/variants",
    tags=["variants"],
)


def parse_oid(pid: str) -> str:
    try:
        ObjectId(pid)
        return pid
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID produit invalide"
        )


@router.get("/", response_model=List[VariantOut])
async def list_variants(
    product_id: str = Path(...), db=Depends(get_db)
):
    pid = parse_oid(product_id)
    raw_vars = await get_variants(db, product_id)
    remapped = []
    for var in raw_vars:
       # Remapper les images de chaque variante :
        imgs = var.get("images", [])
        var["images"] = [
            {
                "id": str(img_doc["_id"]),
                **{k: v for k, v in img_doc.items() if k != "_id"}
            }
            for img_doc in imgs
        ]
        remapped.append(var)
    return remapped


@router.post(
    "/",
    response_model=VariantOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une variante (couleur + tailles)"
)
async def create_variant(
    product_id: str,
    v: VariantCreate,
    db=Depends(get_db),
):
    """
    Body attendu :
    {
      "color": "noir",
      "sizes": [{"size":"S","stock":7},…],
      "images": []
    }
    """
    pid = parse_oid(product_id)
    return await add_variant(db, pid, v.dict())


@router.patch(
    "/{color}/sizes/{size}/stock",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Met à jour le stock d'une taille pour une couleur"
)
async def change_stock(
    product_id: str,
    color: str,
    size: str,
    new_stock: int,
    db=Depends(get_db),
):
    pid = parse_oid(product_id)
    modified = await update_variant_stock(db, pid, color, size, new_stock)
    if not modified:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variante ou taille non trouvée"
        )
    return


@router.post(
    "/{color}/images",
    response_model=ImageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Uploader une image pour la variante couleur"
)
async def upload_variant_color_image(
    product_id: str,
    color: str,
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    """
    Multipart/form-data { file: <l'image> }
    """
    pid = parse_oid(product_id)

    # 1) upload sur ImageKit
    url = await upload_to_imagekit(file)

    # 2) stocker l'objet image { id, url } dans variants.$.images
    return await add_image_to_variant(db, pid, color, {"url": url})


@router.delete(
    "/{color}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une image de la variante couleur"
)
async def delete_variant_color_image(
    product_id: str,
    color: str,
    image_id: str,
    db=Depends(get_db),
):
    pid = parse_oid(product_id)
    success = await remove_image_from_variant(db, pid, color, image_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image non trouvée"
        )
    return
