# app/schemas/image.py
from pydantic import BaseModel, HttpUrl
from typing import List, Optional

class ImageCreate(BaseModel):
    url: HttpUrl
    alt_text: Optional[str] = None
    order: Optional[int] = None

class ImageOut(ImageCreate):
    id: str
    url: HttpUrl
    class Config:
        from_attributes = True
        
class ImageUploadOut(BaseModel):
    url: HttpUrl

    class Config:
        from_attributes = True

class MultipleImageUploadOut(BaseModel):
    urls: List[str]