from pydantic import BaseModel, Field
from typing import Optional, List, Dict

from models.image import ImageModel
from .utils import PyObjectId

class ProductModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    # Identification
    style_id: str
    name: str
    full_name: str
    sku: Optional[str] = None

    # Positionnement
    style: str
    season: str
    target_audience: str
    inspiration: str

    # Tarification & stock
    price: float
    in_stock: bool = True

    # Descriptif & visuel
    description: Optional[str] = None
    packaging: str

    # Tissu & grammage
    fabric: str
    composition: Dict[str, float]
    grammage: str

    # Col & fermeture
    collar_type: str
    zip_type: str
    zip_length_cm: float
    zip_color_options: List[str]

    # Finitions
    sleeve_finish: str
    hem_finish: str

    # Branding & étiquette
    logo_placement: str
    label_detail: str

    # Broderie / embossage
    embroidery_position: Optional[str] = None
    embroidery_text:    Optional[str] = None
    embroidery_size_cm: Optional[str] = None
    embroidery_color:   Optional[str] = None
    alternative_marking: Optional[str] = None

    # Entretien
    care_instructions: str

    # Nouvelle section « images »
    images: List[ImageModel] = []   # liste d’objets ImageModel

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
