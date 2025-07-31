# app/schemas/wishlist.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List

class WishlistCreate(BaseModel):
    product_id: str = Field(..., description="ID du produit à ajouter")

class WishlistOut(BaseModel):
    id: str
    user_id: str
    product_id: str
    added_at: datetime

class WishlistList(BaseModel):
    items: List[WishlistOut]
