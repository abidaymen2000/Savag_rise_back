# app/schemas/variant.py
from pydantic import BaseModel
from typing import List

from app.schemas.image import ImageOut

class SizeStock(BaseModel):
    size: str
    stock: int

class VariantCreate(BaseModel):
    color: str
    sizes: List[SizeStock]           # on reçoit toutes les tailles & stocks
    images: List[str] = []           # URLs (initialement vide)

class VariantOut(VariantCreate):
    color: str
    sizes: List[SizeStock]
    images: List[ImageOut] = []   # on renvoie des objets ImageOut { id, url }

    class Config:
        orm_mode = True
