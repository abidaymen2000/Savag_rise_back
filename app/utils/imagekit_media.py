import base64
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from imagekitio.models.results.UploadFileResult import UploadFileResult

from app.schemas.vlog import MediaType

from .imagekit_client import ik

VLOG_MEDIA_FOLDERS = {
    "concept-image": "/store-savage-rise/vlog/concept",
    "concept-video": "/store-savage-rise/vlog/concept",
    "chapter-cover": "/store-savage-rise/vlog/chapters",
    "chapter-trailer": "/store-savage-rise/vlog/chapters",
    "episode-video": "/store-savage-rise/vlog/episodes",
    "episode-thumbnail": "/store-savage-rise/vlog/episodes",
    "short-film": "/store-savage-rise/vlog/short-films",
}

IMAGE_TYPES = {"concept-image", "chapter-cover", "episode-thumbnail"}
VIDEO_TYPES = {"concept-video", "chapter-trailer", "episode-video", "short-film"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}


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


def _validate_media(file: UploadFile, media_type: MediaType) -> None:
    content_type = file.content_type or ""
    suffix = Path(file.filename or "").suffix.lower()
    if media_type in IMAGE_TYPES and not (content_type.startswith("image/") or suffix in IMAGE_EXTENSIONS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le fichier doit etre une image")
    if media_type in VIDEO_TYPES and not (content_type.startswith("video/") or suffix in VIDEO_EXTENSIONS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le fichier doit etre une video")


async def upload_vlog_media_to_imagekit(file: UploadFile, media_type: MediaType) -> Dict[str, Any]:
    _validate_media(file, media_type)

    file_bytes = await file.read()
    file_base64 = base64.b64encode(file_bytes).decode("ascii")
    opts = UploadFileRequestOptions(
        folder=VLOG_MEDIA_FOLDERS[media_type],
        use_unique_file_name=True,
    )

    def do_upload():
        return ik.upload_file(file=file_base64, file_name=file.filename, options=opts)

    try:
        res = await run_in_threadpool(do_upload)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Echec de l'upload ImageKit : {e}")

    if not isinstance(res, UploadFileResult):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Reponse inattendue : {res!r}")

    asset = _asset_from_result(res)
    if not asset["url"]:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Aucune URL dans la reponse : {res!r}")

    return asset
