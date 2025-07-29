import os
from uuid import uuid4
from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from typing import List


from ..db import get_db
from .. import crud
from ..schemas.image import ImageUploadOut
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
    return [
        ProductOut(id=str(p["_id"]), **{k: v for k, v in p.items() if k != "_id"})
        for p in prods
    ]

@router.get("/{product_id}", response_model=ProductOut)
async def read_product(product_id: str, db=Depends(get_db)):
    try:
        oid = ObjectId(product_id)
    except:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID produit invalide")
    prod = await crud.get_product(db, product_id)
    if not prod:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouvé")
    return ProductOut(id=str(prod["_id"]), **{k: v for k, v in prod.items() if k != "_id"})

@router.post(
    "/{product_id}/upload-image",
    response_model=ImageUploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload une image puis l'ajoute à la collection du produit"
)
async def upload_image_to_product(
    product_id: str,
    request: Request,
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    # 1) Vérifier l'ID et existence du produit
    try:
        oid = ObjectId(product_id)
    except:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID produit invalide")
    prod = await db["products"].find_one({"_id": oid})
    if not prod:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouvé")

    # 2) Vérifier le type de fichier
    if not file.content_type.startswith("image/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le fichier doit être une image")

    # 3) Générer un nom unique et sauvegarder
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid4()}{ext}"
    upload_dir = os.path.join(os.getcwd(), "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    # 4) Construire l'URL publique
    url = f"{request.base_url}static/uploads/{filename}"

    # 5) Calculer l'ordre et mettre à jour Mongo
    current = prod.get("images", [])
    next_order = len(current) + 1
    image_doc = {"url": url, "alt_text": None, "order": next_order}
    await db["products"].update_one(
        {"_id": oid},
        {"$push": {"images": image_doc}}
    )

    # 6) Retourner l'URL construite (string)
    return ImageUploadOut(url=url)


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
        oid = ObjectId(product_id)
    except:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID produit invalide")

    existing = await crud.get_product(db, product_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouvé")

    updated = await crud.update_product(db, product_id, product)
    if not updated:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Échec lors de la mise à jour du produit"
        )

    # Reconstruire la réponse sans _id
    return ProductOut(id=str(updated["_id"]), **{
        k: v for k, v in updated.items() if k != "_id"
    })


@router.delete(
    "/{product_id}/images/{order}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprime une image d'un produit et son fichier"
)
async def delete_product_image(
    product_id: str,
    order: int,
    db=Depends(get_db)
):
    # … ton code existant …
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprime un produit et ses images du disque et de la base"
)
async def delete_product(
    product_id: str,
    db=Depends(get_db)
):
    try:
        oid = ObjectId(product_id)
    except:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID produit invalide")

    prod = await crud.get_product(db, product_id)
    if not prod:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouvé")

    # Suppression des fichiers
    for img in prod.get("images", []):
        fname = img["url"].rsplit("/static/uploads/", 1)[-1]
        path = os.path.join(os.getcwd(), "static", "uploads", fname)
        if os.path.isfile(path):
            os.remove(path)

    await crud.delete_product(db, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
