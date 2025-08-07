import os
from uuid import uuid4
from bson import ObjectId
from fastapi import (
    APIRouter, Depends, HTTPException, Query,
    status, Response
)
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, DESCENDING

from app.crud.product import get_product

from ..db import get_db
from .. import crud
from ..schemas.product import ProductCreate, ProductUpdate, ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, db=Depends(get_db)):
    created = await crud.create_product(db, product)
    return ProductOut(id=str(created["_id"]), **{
        k: v for k, v in created.items() if k != "_id"
    })


@router.get("/", response_model=List[ProductOut])
async def list_products(skip: int = 0, limit: int = 10, db=Depends(get_db)):
    prods = await crud.get_products(db, skip, limit)
    results = []
    for p in prods:
        # 1) Extraire tous les champs sauf _id
        payload = {k: v for k, v in p.items() if k != "_id"}
        # 2) Ajouter l'id racine
        payload["id"] = str(p["_id"])

        # 3) Remapper les variants et leurs images
        remapped_variants = []
        for var in payload.get("variants", []):
            # Pour chaque image, on crée {"id": ..., **autres champs}
            remapped_images = [
                {
                    "id": str(img_doc["_id"]),
                    **{k: v for k, v in img_doc.items() if k != "_id"}
                }
                for img_doc in var.get("images", [])
            ]
            var["images"] = remapped_images
            remapped_variants.append(var)
        payload["variants"] = remapped_variants

        # 4) Instancier le modèle Pydantic
        results.append(ProductOut(**payload))

    return results

@router.get(
    "/search",
    response_model=List[ProductOut],
    summary="Recherche plein-texte + filtres + tri + pagination"
)
async def search_products_endpoint(
    text: Optional[str] = Query(None, description="Terme plein-texte"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    color: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort: Optional[str] = Query(
        None,
        regex="^(price|full_name):(asc|desc)$"
    ),
    db=Depends(get_db),
):
    # Création du pipeline d'agrégation
    pipeline = []
    filt: dict = {}
    if text:
        filt["$text"] = {"$search": text}
    if min_price is not None or max_price is not None:
        pf: dict = {}
        if min_price is not None:
            pf["$gte"] = min_price
        if max_price is not None:
            pf["$lte"] = max_price
        filt["price"] = pf
    if color or size:
        em: dict = {}
        if color:
            em["color"] = color
        if size:
            em["size"] = size
        filt["variants"] = {"$elemMatch": em}
    if filt:
        pipeline.append({"$match": filt})
    if sort:
        field, direction = sort.split(":")
        dir_flag = ASCENDING if direction == "asc" else DESCENDING
        pipeline.append({"$sort": {field: dir_flag}})
    pipeline += [{"$skip": skip}, {"$limit": limit}]

    raw = await db["products"].aggregate(pipeline).to_list(length=limit)
    results = []
    for doc in raw:
        doc["id"] = str(doc["_id"])
        results.append(doc)
    return results


@router.put(
    "/{product_id}",
    response_model=ProductOut,
    summary="Met à jour un produit existant"
)
async def update_product_endpoint(
    product_id: str,
    product: ProductUpdate,
    db=Depends(get_db)
):
    try:
        ObjectId(product_id)
    except:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID invalide")

    existing = await crud.get_product(db, product_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouvé")

    updated = await crud.update_product(db, product_id, product)
    if not updated:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Échec lors de la mise à jour"
        )

    return ProductOut(id=str(updated["_id"]), **{
        k: v for k, v in updated.items() if k != "_id"
    })


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprime un produit et ses variantes"
)
async def delete_product(
    product_id: str,
    db=Depends(get_db)
):
    try:
        ObjectId(product_id)
    except:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID invalide")

    prod = await crud.get_product(db, product_id)
    if not prod:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouvé")

    await crud.delete_product(db, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Récupère un produit par son ID"
)
async def get_product_endpoint(
    product_id: str,
    db=Depends(get_db)
):
    # 1) Valide l'ID
    try:
        ObjectId(product_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID invalide"
        )

    # 2) Récupère en base
    prod = await get_product(db, product_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produit non trouvé"
        )

    # 3) Remappe _id → id et construit le payload
    payload: Dict[str, Any] = {k: v for k, v in prod.items() if k != "_id"}
    payload["id"] = str(prod["_id"])

    # 4) Remappe les variants et leurs images
    remapped_variants = []
    for var in payload.get("variants", []):
        remapped_images = [
            {
                "id": str(img_doc["_id"]),
                **{ik: iv for ik, iv in img_doc.items() if ik != "_id"}
            }
            for img_doc in var.get("images", [])
        ]
        var["images"] = remapped_images
        remapped_variants.append(var)
    payload["variants"] = remapped_variants

    # 5) Retourne via Pydantic
    return ProductOut(**payload)