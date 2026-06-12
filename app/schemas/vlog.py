from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ChapterStatus = Literal["draft", "coming_soon", "active", "completed", "archived"]
EpisodeStatus = Literal["draft", "coming_soon", "released", "hidden"]
MediaType = Literal["concept-image", "concept-video", "chapter-cover", "chapter-trailer", "episode-video", "episode-thumbnail", "short-film"]
VlogCommentStatus = Literal["visible", "hidden"]


class VlogMediaAsset(BaseModel):
    file_id: Optional[str] = None
    name: Optional[str] = None
    url: str
    thumbnail_url: Optional[str] = None
    file_path: Optional[str] = None
    mime: Optional[str] = None
    size: Optional[int] = None


class ImageKitDirectUploadAuth(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    token: str
    expire: int
    signature: str
    public_key: str = Field(..., alias="publicKey")
    url_endpoint: str = Field(..., alias="urlEndpoint")
    folder: str


class VlogMediaRegister(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    media_type: MediaType
    file_id: Optional[str] = Field(None, alias="fileId")
    name: Optional[str] = None
    url: str
    thumbnail_url: Optional[str] = Field(None, alias="thumbnailUrl")
    file_path: Optional[str] = Field(None, alias="filePath")
    mime: Optional[str] = None
    size: Optional[int] = None


class VlogMediaOut(VlogMediaRegister):
    id: str
    created_at: datetime


class VlogSettingsBase(BaseModel):
    title: str = "Savage Rise Chapters"
    subtitle: Optional[str] = "Every 3 drops tell one story"
    description: str = "Each chapter unfolds through 3 episodes, connected to drops, products and a final short movie."
    hero_image_url: Optional[str] = None
    hero_video_url: Optional[str] = None
    is_active: bool = True


class VlogSettingsUpdate(VlogSettingsBase):
    pass


class VlogSettingsOut(VlogSettingsBase):
    updated_at: Optional[datetime] = None


class ShortFilm(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    release_date: Optional[datetime] = None
    is_released: bool = False


class ShortFilmUpdate(ShortFilm):
    pass


class VlogChapterBase(BaseModel):
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    trailer_video_url: Optional[str] = None
    status: ChapterStatus = "draft"
    order: int = 0
    release_date: Optional[datetime] = None
    short_film: Optional[ShortFilm] = None


class VlogChapterCreate(VlogChapterBase):
    pass


class VlogChapterUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    trailer_video_url: Optional[str] = None
    status: Optional[ChapterStatus] = None
    order: Optional[int] = None
    release_date: Optional[datetime] = None
    short_film: Optional[ShortFilm] = None


class VlogChapterOut(VlogChapterBase):
    id: str
    slug: str
    created_at: datetime
    updated_at: datetime


class VlogEpisodeBase(BaseModel):
    episode_number: int = Field(..., ge=1, le=3)
    title: str
    description: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    release_date: Optional[datetime] = None
    status: EpisodeStatus = "draft"
    linked_product_ids: List[str] = Field(default_factory=list)
    order: int = 0


class VlogEpisodeCreate(VlogEpisodeBase):
    pass


class VlogEpisodeUpdate(BaseModel):
    episode_number: Optional[int] = Field(None, ge=1, le=3)
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    release_date: Optional[datetime] = None
    status: Optional[EpisodeStatus] = None
    linked_product_ids: Optional[List[str]] = None
    order: Optional[int] = None


class ProductSummary(BaseModel):
    id: str
    name: str
    full_name: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    in_stock: bool = True


class VlogEpisodeOut(VlogEpisodeBase):
    id: str
    chapter_id: str
    products: List[ProductSummary] = Field(default_factory=list)
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    liked_by_current_user: bool = False
    created_at: datetime
    updated_at: datetime


class VlogChapterWithEpisodesOut(VlogChapterOut):
    episodes: List[VlogEpisodeOut] = Field(default_factory=list)


class VlogPageOut(BaseModel):
    settings: VlogSettingsOut
    chapters: List[VlogChapterWithEpisodesOut] = Field(default_factory=list)


class VlogEpisodeViewOut(BaseModel):
    episode_id: str
    view_count: int


class VlogEpisodeLikeOut(BaseModel):
    episode_id: str
    liked: bool
    like_count: int


class VlogCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class VlogCommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=1000)
    status: Optional[VlogCommentStatus] = None


class VlogCommentOut(BaseModel):
    id: str
    episode_id: str
    user_id: str
    content: str
    status: VlogCommentStatus = "visible"
    author: Optional[str] = None
    episode_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedVlogCommentsOut(BaseModel):
    items: List[VlogCommentOut] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int
