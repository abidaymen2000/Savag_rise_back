import base64
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from imagekitio.models.ListAndSearchFileRequestOptions import ListAndSearchFileRequestOptions
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from imagekitio.models.results.ListFileResult import ListFileResult
from imagekitio.models.results.UploadFileResult import UploadFileResult

from .imagekit_client import ik

HEADER_VIDEO_FOLDER = "/store-savage-rise/header-videos"
HEADER_IMAGE_FOLDER = "/store-savage-rise/header-images"
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _asset_from_result(result: Any) -> Dict[str, Any]:
    return {
        "file_id": getattr(result, "file_id", None),
        "name": getattr(result, "name", None),
        "url": getattr(result, "url", None),
        "thumbnail_url": getattr(result, "thumbnail_url", None) or getattr(result, "thumbnail", None),
        "file_path": getattr(result, "file_path", None),
        "mime": getattr(result, "mime", None),
        "size": getattr(result, "size", None),
    }


def _is_video_asset(asset: Dict[str, Any]) -> bool:
    mime = asset.get("mime")
    name = asset.get("name") or asset.get("file_path") or ""
    if mime and mime.startswith("video/"):
        return True
    return Path(name).suffix.lower() in VIDEO_EXTENSIONS


def _is_image_asset(asset: Dict[str, Any]) -> bool:
    mime = asset.get("mime")
    name = asset.get("name") or asset.get("file_path") or ""
    if mime and mime.startswith("image/"):
        return True
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS


async def upload_header_video_to_imagekit(file: UploadFile) -> Dict[str, Any]:
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le fichier doit etre une video")

    file_bytes = await file.read()
    file_base64 = base64.b64encode(file_bytes).decode("ascii")
    opts = UploadFileRequestOptions(folder=HEADER_VIDEO_FOLDER, use_unique_file_name=True)

    def do_upload():
        return ik.upload_file(file=file_base64, file_name=file.filename, options=opts)

    try:
        res = await run_in_threadpool(do_upload)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Echec de l'upload video ImageKit : {e}")

    if not isinstance(res, UploadFileResult):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Reponse inattendue : {res!r}")

    asset = _asset_from_result(res)
    if not asset["url"]:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Aucune URL dans la reponse : {res!r}")

    return asset


async def upload_header_image_to_imagekit(file: UploadFile) -> Dict[str, Any]:
    content_type = file.content_type or ""
    suffix = Path(file.filename or "").suffix.lower()
    if not content_type.startswith("image/") and suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le fichier doit etre une image")

    file_bytes = await file.read()
    file_base64 = base64.b64encode(file_bytes).decode("ascii")
    opts = UploadFileRequestOptions(folder=HEADER_IMAGE_FOLDER, use_unique_file_name=True)

    def do_upload():
        return ik.upload_file(file=file_base64, file_name=file.filename, options=opts)

    try:
        res = await run_in_threadpool(do_upload)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Echec de l'upload image ImageKit : {e}")

    if not isinstance(res, UploadFileResult):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Reponse inattendue : {res!r}")

    asset = _asset_from_result(res)
    if not asset["url"]:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Aucune URL dans la reponse : {res!r}")

    return asset


async def list_header_videos_from_imagekit(limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
    opts = ListAndSearchFileRequestOptions(
        type="file",
        sort="DESC_CREATED",
        path=HEADER_VIDEO_FOLDER,
        file_type="all",
        limit=limit,
        skip=skip,
    )

    def do_list():
        return ik.list_files(options=opts)

    try:
        res = await run_in_threadpool(do_list)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Echec de la lecture ImageKit : {e}")

    if not isinstance(res, ListFileResult):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Reponse inattendue : {res!r}")

    return [asset for asset in (_asset_from_result(item) for item in res.list) if asset["url"] and _is_video_asset(asset)]


async def list_header_images_from_imagekit(limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
    opts = ListAndSearchFileRequestOptions(
        type="file",
        sort="DESC_CREATED",
        path=HEADER_IMAGE_FOLDER,
        file_type="all",
        limit=limit,
        skip=skip,
    )

    def do_list():
        return ik.list_files(options=opts)

    try:
        res = await run_in_threadpool(do_list)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Echec de la lecture ImageKit : {e}")

    if not isinstance(res, ListFileResult):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Reponse inattendue : {res!r}")

    return [asset for asset in (_asset_from_result(item) for item in res.list) if asset["url"] and _is_image_asset(asset)]


async def delete_header_video_from_imagekit(file_id: str) -> None:
    def do_delete():
        return ik.delete_file(file_id)

    try:
        await run_in_threadpool(do_delete)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Echec de la suppression ImageKit : {e}")
