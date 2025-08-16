# app/schemas/review.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Note de 1 à 5")
    title: Optional[str] = Field(None, max_length=100)
    comment: Optional[str]

class ReviewCreate(ReviewBase):
    pass   
    

class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str]
    comment: Optional[str]

class ReviewOut(ReviewBase):
    id: str
    user_id: str
    product_id: str 
    created_at: datetime
    updated_at: datetime
    author: Optional[str] = None  # <-- NEW: nom complet ou email

class ReviewStats(BaseModel):
    average_rating: Optional[float]
    count: int
