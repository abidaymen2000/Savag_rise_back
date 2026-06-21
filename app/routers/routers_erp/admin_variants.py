from fastapi import APIRouter, Depends, File, UploadFile, status

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.image import ImageOut
from app.schemas.variant import VariantCreate, VariantOut
from app.services.services_erp import admin_variant_service


router = APIRouter(prefix="/products/{product_id}/variants", tags=["admin-variants"])


@router.post("/", response_model=VariantOut, status_code=status.HTTP_201_CREATED, summary="Creer une variante (couleur + tailles)")
async def create_variant(
    product_id: str,
    variant: VariantCreate,
    db=Depends(get_db),
    _admin=Depends(require_permission("products")),
):
    return await admin_variant_service.create_variant(db, product_id, variant)


@router.patch("/{color}/sizes/{size}/stock", status_code=status.HTTP_204_NO_CONTENT, summary="Met a jour le stock d'une taille pour une couleur")
async def change_stock(
    product_id: str,
    color: str,
    size: str,
    new_stock: int,
    db=Depends(get_db),
    _admin=Depends(require_permission("products")),
):
    await admin_variant_service.update_stock(db, product_id, color, size, new_stock)


@router.post("/{color}/images", response_model=ImageOut, status_code=status.HTTP_201_CREATED, summary="Uploader une image pour la variante couleur")
async def upload_variant_color_image(
    product_id: str,
    color: str,
    file: UploadFile = File(...),
    db=Depends(get_db),
    _admin=Depends(require_permission("products")),
):
    return await admin_variant_service.upload_variant_image(db, product_id, color, file)


@router.delete("/{color}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une image de la variante couleur")
async def delete_variant_color_image(
    product_id: str,
    color: str,
    image_id: str,
    db=Depends(get_db),
    _admin=Depends(require_permission("products")),
):
    await admin_variant_service.delete_variant_image(db, product_id, color, image_id)
