# app/models/variant.py
from typing import List
from pydantic import BaseModel

from .image import ImageModel

class SizeStock(BaseModel):
    size: str
    stock: int

class VariantDB(BaseModel):
    color: str
    size: str
    images: List[ImageModel] = []

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True
        # Si tu utilises PyObjectId ailleurs, tu peux aussi préciser :
        # arbitrary_types_allowed = True
