from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Optional, List

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class AdminPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superadmin: bool
    permissions: List[str] = Field(default_factory=list)
    capabilities: Dict[str, bool] = Field(default_factory=dict)
    available_permissions: List[str] = Field(default_factory=list)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AdminPasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class AdminCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    is_superadmin: bool = False
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = True


class AdminUpdate(BaseModel):
    full_name: Optional[str] = None
    is_superadmin: Optional[bool] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=8)
