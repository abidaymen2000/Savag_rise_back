# app/models/user.py
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from .utils import PyObjectId

class UserModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    full_name: Optional[str] = Field(None, alias="full_name")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
