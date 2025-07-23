import os
from uuid import uuid4
from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from typing import List

from app.schemas.image import ImageUploadOut
from .. import crud, schemas
from ..db import get_db

router = APIRouter(prefix="/products", tags=["products"])

@router.post("/", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(product: schemas.ProductCreate, db=Depends(get_db)):
    created = await crud.create_product(db, product)
    return {"id": str(created["_id"]), **product.dict(), "in_stock": created["in_stock"]}

@router.get("/", response_model=List[schemas.ProductOut])
async def list_products(skip: int = 0, limit: int = 10, db=Depends(get_db)):
    prods = await crud.get_products(db, skip, limit)
    return [{"id": str(p["_id"]), **p} for p in prods]

@router.get("/{product_id}", response_model=schemas.ProductOut)
async def read_product(product_id: str, db=Depends(get_db)):
    prod = await crud.get_product(db, product_id)
    if not prod:
        raise HTTPException(404, "Produit non trouvé")
    return {"id": str(prod["_id"]), **prod}

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
    # 1) Vérifier que le produit existe
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ID produit invalide")
    prod = await db["products"].find_one({"_id": oid})
    if not prod:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produit non trouvé")

    # 2) Vérifier le type de fichier
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Le fichier doit être une image")

    # 3) Générer un nom de fichier unique et sauvegarder
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid4()}{ext}"
    upload_dir = os.path.join(os.getcwd(), "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    # 4) Construire l’URL publique
    url = f"{request.base_url}static/uploads/{filename}"

    # 5) Calculer l’order (place en dernière position)
    current = prod.get("images", [])
    next_order = len(current) + 1

    # 6) Mettre à jour le produit : push dans le tableau images
    image_doc = {"url": url, "alt_text": None, "order": next_order}
    await db["products"].update_one(
        {"_id": oid},
        {"$push": {"images": image_doc}}
    )

    # 7) Retourner l’URL (ImageUploadOut contient juste `url: HttpUrl`)
    return ImageUploadOut(url=url)