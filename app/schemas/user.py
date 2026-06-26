# app/schemas/user.py
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.integrations.meta.schemas import MetaEventContextIn

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    meta: Optional[MetaEventContextIn] = None
    
class UserOut(UserBase):
    id: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str
    
    class Config:
        from_attributes = True
        
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    # tu peux ajouter d’autres champs modifiables, ex. phone, name…
    full_name: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str     = Field(..., min_length=6)
