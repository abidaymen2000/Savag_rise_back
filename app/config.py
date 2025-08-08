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
    
    # 🔥 Ajoutez ces lignes pour ImageKit 🔥
    imagekit_public_key: SecretStr
    imagekit_private_key: SecretStr
    imagekit_url_endpoint: AnyHttpUrl
    
    LOGO_URL: HttpUrl = "https://ik.imagekit.io/deuxug3j0/email-images/SavageRiseEmail.png?updatedAt=1754182758176"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
