from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict

from .image import ImageCreate

class ProductBase(BaseModel):
    # Identification
    style_id: str
    name: str
    full_name: str
    sku: Optional[str] = None

    # Description & visuel
    description: Optional[str] = None
    packaging: Optional[str] = None

    # Positionnement
    style: Optional[str] = None
    season: Optional[str] = None
    target_audience: Optional[str] = None
    inspiration: Optional[str] = None

    # Tissu & grammage
    fabric: Optional[str] = None
    composition: Optional[Dict[str, float]] = None
    grammage: Optional[str] = None

    # Col & zip
    collar_type: Optional[str] = None
    zip_type: Optional[str] = None
    zip_length_cm: Optional[float] = None
    zip_color_options: Optional[List[str]] = None

    # Finitions
    sleeve_finish: Optional[str] = None
    hem_finish: Optional[str] = None

    # Branding & étiquette
    logo_placement: Optional[str] = None
    label_detail: Optional[str] = None

    # Broderie / embossage
    embroidery_position: Optional[str] = None
    embroidery_text: Optional[str] = None
    embroidery_size_cm: Optional[str] = None
    embroidery_color: Optional[str] = None
    alternative_marking: Optional[str] = None

    # Entretien
    care_instructions: Optional[str] = None

class ProductCreate(ProductBase):
    price: float
    in_stock: bool = True
    images: List[ImageCreate] = []

class ProductOut(ProductBase):
    id: str
    price: float
    in_stock: bool
    images: List[ImageCreate] = []

    class Config:
        from_attributes = True
