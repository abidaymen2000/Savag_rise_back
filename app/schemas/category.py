# app/schemas/category.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CategoryBase(BaseModel):
    name: str = Field(..., description="Nom de la catégorie")
    description: Optional[str] = Field(None, description="Description facultative")

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Nouveau nom")
    description: Optional[str] = Field(None, description="Nouvelle description")

class CategoryOut(CategoryBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
