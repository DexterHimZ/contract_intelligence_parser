from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Contract Intelligence Parser"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # MongoDB settings
    MONGODB_URL: str = "mongodb://admin:admin123@localhost:27017/contract_intelligence?authSource=admin"
    DATABASE_NAME: str = "contract_intelligence"

    # Upload settings
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]

    # CORS settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Processing settings
    PROCESSING_TIMEOUT: int = 120  # seconds
    MAX_CONCURRENT_PROCESSING: int = 10

    # OCR settings
    ENABLE_OCR: bool = True
    OCR_LANGUAGE: str = "eng"

    # LLM settings (optional)
    ENABLE_LLM: bool = False
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-3.5-turbo"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()