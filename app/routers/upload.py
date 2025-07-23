from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from ..schemas.image import ImageUploadOut
from uuid import uuid4
import os

router = APIRouter(prefix="", tags=["upload"])

@router.post(
    "/upload-image",
    response_model=ImageUploadOut,
    summary="Upload une image et renvoie son URL publique",
)
async def upload_image(request: Request, file: UploadFile = File(...)):
    # 1) Vérifier le type
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Le fichier doit être une image")

    # 2) Générer un nom unique
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid4()}{ext}"

    # 3) Sauvegarde sur disque
    upload_dir = os.path.join(os.getcwd(), "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    # 4) Construire l’URL publique à partir de base_url (string)
    # request.base_url inclut déjà le trailing slash
    url = f"{request.base_url}static/uploads/{filename}"

    # 5) Retourner ; Pydantic convertira url: str → HttpUrl
    return ImageUploadOut(url=url)
