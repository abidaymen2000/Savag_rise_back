#app/schemas/product.py
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict

from .variant import VariantCreate, VariantOut
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
    categories: List[str] = Field(default_factory=list, description="Liste des catégories associées au produit")

class ProductCreate(ProductBase):
    price: float
    in_stock: bool = True
    variants: Optional[List[VariantCreate]] = []
class ProductOut(ProductBase):
    id: str
    price: float
    in_stock: bool
    variants: List[VariantOut] = []
    class Config:
        from_attributes = True
        
class ProductUpdate(BaseModel):
    style_id: Optional[str] = None
    name: Optional[str] = None
    full_name: Optional[str] = None
    sku: Optional[str] = None

    description: Optional[str] = None
    packaging: Optional[str] = None

    style: Optional[str] = None
    season: Optional[str] = None
    target_audience: Optional[str] = None
    inspiration: Optional[str] = None

    fabric: Optional[str] = None
    composition: Optional[Dict[str, float]] = None
    grammage: Optional[str] = None

    collar_type: Optional[str] = None
    zip_type: Optional[str] = None
    zip_length_cm: Optional[float] = None
    zip_color_options: Optional[List[str]] = None

    sleeve_finish: Optional[str] = None
    hem_finish: Optional[str] = None

    logo_placement: Optional[str] = None
    label_detail: Optional[str] = None

    embroidery_position: Optional[str] = None
    embroidery_text: Optional[str] = None
    embroidery_size_cm: Optional[str] = None
    embroidery_color: Optional[str] = None
    alternative_marking: Optional[str] = None

    care_instructions: Optional[str] = None

    price: Optional[float] = None
    in_stock: Optional[bool] = None

    categories: Optional[List[str]]