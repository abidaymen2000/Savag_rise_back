from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Optional

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: str
    is_active: bool

    class Config:
        from_attributes = True
        
class ImageCreate(BaseModel):
    url: HttpUrl
    alt_text: Optional[str] = None
    order: Optional[int] = None

class ImageOut(ImageCreate):
    id: str

    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    style_id: str
    name: str
    full_name: str
    price: float

class ProductCreate(ProductBase):
    images: List[ImageCreate] = []

class ProductOut(ProductBase):
    id: str
    in_stock: bool
    images: List[ImageOut] = []

    class Config:
        from_attributes = True
        
