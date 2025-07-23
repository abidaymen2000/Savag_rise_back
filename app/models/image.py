from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from .utils import PyObjectId

class ImageModel(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    url: str                          # URL complète de l’image
    alt_text: Optional[str] = None   # Texte alternatif pour l’accessibilité
    order: Optional[int] = None       # Position dans la galerie (1, 2, 3…)

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
        
class ImageUploadOut(BaseModel):
    url: HttpUrl

    class Config:
        from_attributes = True