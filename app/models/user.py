# app/models/user.py
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from .utils import PyObjectId

class UserModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    full_name: Optional[str] = Field(None, alias="full_name")

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
