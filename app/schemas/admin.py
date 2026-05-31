from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class AdminPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    is_superadmin: bool
    permissions: List[str] = []

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AdminPasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
