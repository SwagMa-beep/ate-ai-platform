"""
Application settings for the main ATE AI platform.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

BASE_DIR = Path(
    os.environ.get(
        "ATE_BASE_DIR",
        Path(__file__).resolve().parent.parent.parent.parent,
    )
)


class Settings(BaseSettings):
    # Default text model
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Optional unified chat / vision overrides
    CHAT_API_KEY: str = ""
    CHAT_BASE_URL: str = ""
    CHAT_MODEL: str = ""
    VISION_API_KEY: str = ""
    VISION_BASE_URL: str = ""
    VISION_MODEL: str = ""

    # Project metadata
    PROJECT_NAME: str = "ATE-AI-Platform"
    VERSION: str = "0.2.0"
    DEBUG: bool = True

    # Paths
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    RAW_DIR: Path = BASE_DIR / "data" / "raw"
    LOG_DIR: Path = BASE_DIR / "logs"
    WORKSPACE_MEMORY_PATH: Path = BASE_DIR / "data" / "processed" / "workspace_memory.json"
    WORKSPACE_MEMORY_MAX_ITEMS: int = 20

    # PDF extraction
    MAX_PAGES_PER_BATCH: int = 10
    MAX_TEXT_LENGTH: int = 6000
    ENABLE_PDF_OCR_FALLBACK: bool = True
    PDF_OCR_MIN_CHARS: int = 500
    PDF_OCR_DPI: int = 200

    # Extraction / generation
    MAX_WORKERS: int = 5
    TEMPERATURE: float = 0
    MAX_TOKENS: int = 8192
    CONFIDENCE_THRESHOLD: float = 0.75

    # STS8200S platform constraints
    STS8200S_VI_VOLTAGE_MAX: float = 10.0
    STS8200S_VI_CURRENT_MAX: float = 0.2
    STS8200S_DIO_CHANNELS: int = 24
    STS8200S_CBIT_CHANNELS: int = 40

    # Frontend / networking
    ALLOWED_ORIGINS: list[str] = ["*"]
    CLEAR_PROXY_ENV: bool = False
    SSL_VERIFY: bool = True

    # Chip detection
    ENABLE_CHIP_TYPE_DETECTION: bool = True
    DEFAULT_CHIP_TYPE: str = "UNKNOWN"

    class Config:
        env_file = str(BASE_DIR / "backend" / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_value(cls, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "debug", "dev", "development"}:
            return True
        if text in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return False

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def normalize_allowed_origins(cls, value):
        if isinstance(value, list):
            return value
        if value is None:
            return ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:18080"]
        text = str(value).strip()
        if not text:
            return ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:18080"]
        if text == "*":
            return ["*"]
        return [item.strip() for item in text.split(",") if item.strip()]

    def create_dirs(self):
        for dir_path in [
            self.UPLOAD_DIR,
            self.PROCESSED_DIR,
            self.RAW_DIR,
            self.LOG_DIR,
            self.WORKSPACE_MEMORY_PATH.parent,
            self.UPLOAD_DIR / "chat_images",
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_text_api_key(self) -> str:
        return self.CHAT_API_KEY or self.DEEPSEEK_API_KEY

    def get_text_base_url(self) -> str:
        return self.CHAT_BASE_URL or self.DEEPSEEK_BASE_URL

    def get_text_model(self) -> str:
        return self.CHAT_MODEL or self.DEEPSEEK_MODEL

    def get_text_backend(self) -> str:
        return "chat" if self.CHAT_API_KEY and self.CHAT_BASE_URL and self.CHAT_MODEL else "deepseek"

    def has_vision_model(self) -> bool:
        return bool(self.VISION_API_KEY and self.VISION_BASE_URL and self.VISION_MODEL)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings", "BASE_DIR"]
