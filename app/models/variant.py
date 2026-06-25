from typing import List

from pydantic import BaseModel, Field

from .image import ImageModel


class SizeStockModel(BaseModel):
    size: str
    stock_on_hand: int = 0
    stock_reserved: int = 0


class VariantDB(BaseModel):
    color: str
    sizes: List[SizeStockModel] = Field(default_factory=list)
    images: List[ImageModel] = Field(default_factory=list)

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True
