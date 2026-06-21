# app/schemas/variant.py
from pydantic import BaseModel, Field
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


class VariantColorUpdate(BaseModel):
    color: str = Field(..., min_length=1, max_length=100)


class VariantSizeCreate(BaseModel):
    size: str = Field(..., min_length=1, max_length=50)
    stock: int = Field(0, ge=0)


class VariantInventoryOut(BaseModel):
    color: str
    sizes: List[SizeStock]
