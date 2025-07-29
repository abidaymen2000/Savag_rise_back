# app/models/variant.py
from pydantic import BaseModel

class VariantDB(BaseModel):
    color: str
    size: str
    stock: int

    class Config:
        orm_mode = True
        # Si tu utilises PyObjectId ailleurs, tu peux aussi préciser :
        # arbitrary_types_allowed = True
