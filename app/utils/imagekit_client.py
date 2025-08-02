# app/utils/imagekit_client.py

from imagekitio import ImageKit
from app.config import settings

ik = ImageKit(
    public_key=settings.imagekit_public_key.get_secret_value(),
    private_key=settings.imagekit_private_key.get_secret_value(),
    url_endpoint=settings.imagekit_url_endpoint  # c'est déjà un AnyHttpUrl
)
