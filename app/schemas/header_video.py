from typing import List, Optional

from pydantic import BaseModel, Field


class HeaderVideoAsset(BaseModel):
    file_id: Optional[str] = None
    name: Optional[str] = None
    url: str
    thumbnail_url: Optional[str] = None
    file_path: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = None


class HeaderVideoContent(BaseModel):
    title: str = "NEW COLLECTION"
    subtitle: str = "FALL/WINTER 2025"
    description: str = "Discover redefined elegance"


class HeaderVideoConfig(HeaderVideoContent):
    video: HeaderVideoAsset


class HeaderVideoUpdate(HeaderVideoContent):
    video: HeaderVideoAsset


class HeaderVideoUploadOut(HeaderVideoConfig):
    pass


class HeaderVideoListOut(BaseModel):
    items: List[HeaderVideoAsset] = Field(default_factory=list)
