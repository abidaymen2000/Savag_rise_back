from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas.header_video import HeaderVideoConfig
from app.services.services_store.header_video_service import get_header_video_config


router = APIRouter(tags=["header-video"])

@router.get("/storefront/header-video", response_model=HeaderVideoConfig)
async def read_storefront_header_video(db=Depends(get_db)):
    return await get_header_video_config(db)
