# app/schemas/variant.py
from typing import List

from pydantic import BaseModel, Field

from app.schemas.image import ImageOut


class SizeStock(BaseModel):
    size: str
    stock: int


class SizeStockOut(SizeStock):
    meta_content_id: str


class VariantCreate(BaseModel):
    color: str
    sizes: List[SizeStock]
    images: List[str] = []


class VariantOut(VariantCreate):
    color: str
    meta_content_id: str
    sizes: List[SizeStockOut]
    images: List[ImageOut] = []

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
