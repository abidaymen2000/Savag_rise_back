import io
import base64
from fastapi import UploadFile, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from imagekitio.models.results.UploadFileResult import UploadFileResult
from .imagekit_client import ik

async def upload_to_imagekit(file: UploadFile) -> str:
    # Vérif MIME
    if not file.content_type.startswith("image/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le fichier doit être une image")

    # Lecture brute du binaire
    file_bytes = await file.read()

    # Encodage Base64 (le paramètre file accepte URL/Base64/Binary) :contentReference[oaicite:0]{index=0}
    file_base64 = base64.b64encode(file_bytes).decode("ascii")

    opts = UploadFileRequestOptions(folder="uploads", use_unique_file_name=False)

    def do_upload():
        # on passe la chaîne Base64
        return ik.upload_file(
            file=file_base64,
            file_name=file.filename,
            options=opts
        )

    try:
        res = await run_in_threadpool(do_upload)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Échec de l’upload ImageKit : {e}")

    # Extraction de l’URL
    if not isinstance(res, UploadFileResult):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Réponse inattendue : {res!r}")

    url = getattr(res, "url", None)
    if not url:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Aucune URL dans la réponse : {res!r}")

    return url
