from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Any, Dict, Optional, List
import re

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
    available_permissions: List[Dict[str, Any]] = Field(default_factory=list)
    nav_items: List[Dict[str, Any]] = Field(default_factory=list)

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


class CmsPageCreate(BaseModel):
    key: str = Field(..., min_length=2, max_length=80)
    label: str = Field(..., min_length=2, max_length=120)
    section: str = Field(..., min_length=2, max_length=80)
    path: str = Field(..., min_length=1, max_length=200)
    icon: Optional[str] = Field(None, max_length=80)
    order: int = 1000
    is_active: bool = True
    requires_permission: bool = True

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        key = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9_:-]+", key):
            raise ValueError("La cle permission doit contenir seulement lettres, chiffres, _, : ou -")
        return key

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = value.strip()
        if not path.startswith("/"):
            raise ValueError("Le chemin doit commencer par /")
        return path


class CmsPageUpdate(BaseModel):
    label: Optional[str] = None
    section: Optional[str] = None
    path: Optional[str] = None
    icon: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None
    requires_permission: Optional[bool] = None

    @field_validator("path")
    @classmethod
    def validate_optional_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        path = value.strip()
        if not path.startswith("/"):
            raise ValueError("Le chemin doit commencer par /")
        return path
