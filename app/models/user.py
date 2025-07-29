# app/models/user.py
from pydantic import BaseModel, Field, EmailStr
from .utils import PyObjectId

class UserModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    email: EmailStr
    hashed_password: str
    is_active: bool = True

    class Config:
        validate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
