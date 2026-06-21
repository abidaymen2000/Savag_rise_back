from fastapi import HTTPException, UploadFile, status

from app.crud import header_video as header_video_crud
from app.schemas.header_video import HeaderVideoAsset, HeaderVideoConfig, HeaderVideoListOut, HeaderVideoUpdate, HeaderVideoUploadOut
from app.services.services_cms.imagekit_video import (
    delete_header_video_from_imagekit,
    list_header_images_from_imagekit,
    list_header_videos_from_imagekit,
    upload_header_image_to_imagekit,
    upload_header_video_to_imagekit,
)


def doc_to_config(doc) -> HeaderVideoConfig:
    return HeaderVideoConfig(**doc["value"])


async def get_header_video_config(db) -> HeaderVideoConfig:
    doc = await header_video_crud.find_header_video_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune video de header configuree")
    return doc_to_config(doc)


async def save_header_config(db, config: HeaderVideoConfig) -> HeaderVideoConfig:
    value = config.model_dump()
    await header_video_crud.save_header_video_config(db, value)
    return HeaderVideoConfig(**value)


async def list_header_videos(limit: int, skip: int) -> HeaderVideoListOut:
    return HeaderVideoListOut(items=await list_header_videos_from_imagekit(limit=limit, skip=skip))


async def list_header_images(limit: int, skip: int) -> HeaderVideoListOut:
    return HeaderVideoListOut(items=await list_header_images_from_imagekit(limit=limit, skip=skip))


async def update_header_video(db, payload: HeaderVideoUpdate) -> HeaderVideoConfig:
    return await save_header_config(db, HeaderVideoConfig(**payload.model_dump()))


async def upload_header_video(db, file: UploadFile, set_active: bool) -> HeaderVideoUploadOut:
    asset = await upload_header_video_to_imagekit(file)
    doc = await header_video_crud.find_header_video_doc(db)
    config = doc_to_config(doc) if doc else HeaderVideoConfig(video=asset)
    config.video = asset
    if set_active:
        await save_header_config(db, config)
    return HeaderVideoUploadOut(**config.model_dump())


async def upload_header_image(db, file: UploadFile, set_active: bool) -> HeaderVideoUploadOut:
    asset = await upload_header_image_to_imagekit(file)
    doc = await header_video_crud.find_header_video_doc(db)
    if not doc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Configurez d'abord une video hero")
    config = doc_to_config(doc)
    if set_active:
        config.image = asset
        await save_header_config(db, config)
    return HeaderVideoUploadOut(**config.model_dump())


async def select_header_image(db, image: HeaderVideoAsset) -> HeaderVideoConfig:
    config = await get_header_video_config(db)
    config.image = image
    return await save_header_config(db, config)


async def delete_header_video(db, file_id: str) -> None:
    await delete_header_video_from_imagekit(file_id)
    await header_video_crud.delete_header_video_config_for_file(db, file_id)


async def delete_header_image(db, file_id: str) -> None:
    await delete_header_video_from_imagekit(file_id)
    await header_video_crud.unset_header_image_for_file(db, file_id)
