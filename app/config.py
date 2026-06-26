# app/config.py
import certifi
from pydantic import AnyHttpUrl, HttpUrl, SecretStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MongoDB
    MONGODB_URL: str
    MONGODB_DB_NAME: str

    # JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # SMTP (envois d’emails)
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM: str

    # Admin (notification de commandes)
    ADMIN_EMAIL: str

    # Front-end URL (pour lien de vérification)
    FRONTEND_URL: str
    BACKEND_URL:str

    # Meta catalog feed
    META_CATALOG_BRAND: str = "Savage Rise"
    META_CATALOG_CURRENCY: str = "TND"
    META_PRODUCT_PATH_TEMPLATE: str = "/products/{id}"
    META_PIXEL_ID: str | None = None
    META_CONVERSIONS_API_TOKEN: SecretStr | None = None
    META_CAPI_ENABLED: bool = False
    META_GRAPH_API_VERSION: str = "v23.0"
    META_TEST_EVENT_CODE: str | None = None
    META_OUTBOX_POLL_INTERVAL_SECONDS: int = 15
    META_OUTBOX_LOCK_TIMEOUT_SECONDS: int = 120
    META_OUTBOX_MAX_ATTEMPTS: int = 5
    META_OUTBOX_MAX_BACKOFF_SECONDS: int = 3600
    TRUST_PROXY_HEADERS: bool = True
    TRUSTED_PROXY_HOPS: int = 1
    REQUIRE_MONGO_TRANSACTIONS: bool = True
    
    # 🔥 Ajoutez ces lignes pour ImageKit 🔥
    imagekit_public_key: SecretStr
    imagekit_private_key: SecretStr
    imagekit_url_endpoint: AnyHttpUrl
    
    LOGO_URL: HttpUrl = "https://ik.imagekit.io/deuxug3j0/email-images/SavageRiseEmail.png?updatedAt=1754182758176"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
