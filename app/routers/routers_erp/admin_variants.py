from fastapi import APIRouter, Depends, File, UploadFile, status

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.image import ImageOut
from app.schemas.variant import (
    VariantColorUpdate,
    VariantCreate,
    VariantInventoryOut,
    VariantOut,
    VariantSizeCreate,
)
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


@router.patch("/{color}", response_model=VariantInventoryOut, summary="Renommer la couleur d'une variante")
async def rename_variant_color(
    product_id: str,
    color: str,
    payload: VariantColorUpdate,
    db=Depends(get_db),
    admin=Depends(require_permission("products")),
):
    return await admin_variant_service.rename_color(db, product_id, color, payload, admin)


@router.post(
    "/{color}/sizes",
    response_model=VariantInventoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter une taille a une couleur existante",
)
async def add_variant_size(
    product_id: str,
    color: str,
    payload: VariantSizeCreate,
    db=Depends(get_db),
    admin=Depends(require_permission("products")),
):
    return await admin_variant_service.add_size(db, product_id, color, payload, admin)


@router.patch(
    "/{color}/sizes/{size}/stock-on-hand",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Met a jour le stock physique d'une taille pour une couleur",
)
async def change_stock(
    product_id: str,
    color: str,
    size: str,
    new_stock_on_hand: int,
    db=Depends(get_db),
    _admin=Depends(require_permission("products")),
):
    await admin_variant_service.update_stock(db, product_id, color, size, new_stock_on_hand)


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
