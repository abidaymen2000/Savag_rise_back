# app/schemas/variant.py
from pydantic import BaseModel
from typing import List

class VariantBase(BaseModel):
    color: str
    size: str

class VariantCreate(VariantBase):
    stock: int

class VariantOut(VariantBase):
    stock: int

    class Config:
        orm_mode = True
