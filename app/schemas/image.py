from pydantic import BaseModel, HttpUrl
from typing import Optional

class ImageCreate(BaseModel):
    url: HttpUrl
    alt_text: Optional[str] = None
    order: Optional[int] = None

class ImageOut(ImageCreate):
    id: str

    class Config:
        from_attributes = True
