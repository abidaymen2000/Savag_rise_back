# app/schemas/review.py
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

ReviewStatus = Literal["visible", "hidden"]

class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Note de 1 à 5")
    title: Optional[str] = Field(None, max_length=100)
    comment: Optional[str]

class ReviewCreate(ReviewBase):
    pass   
    

class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = None
    comment: Optional[str] = None

class AdminReviewUpdate(ReviewUpdate):
    status: Optional[ReviewStatus] = None

class ReviewOut(ReviewBase):
    id: str
    user_id: str
    product_id: str 
    status: ReviewStatus = "visible"
    created_at: datetime
    updated_at: datetime
    author: Optional[str] = None  # <-- NEW: nom complet ou email
    product_name: Optional[str] = None

class ReviewStats(BaseModel):
    average_rating: Optional[float]
    count: int

class PaginatedReviewsOut(BaseModel):
    items: List[ReviewOut] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int
