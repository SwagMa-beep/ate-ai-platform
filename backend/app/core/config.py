"""
配置管理模块
统一管理所有配置项
"""
import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import field_validator

# 获取项目根目录
BASE_DIR = Path(
    os.environ.get(
        "ATE_BASE_DIR",
        Path(__file__).resolve().parent.parent.parent.parent,
    )
)

class Settings(BaseSettings):
    """项目配置"""

    # ========== API配置 ==========
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ========== 项目信息 ==========
    PROJECT_NAME: str = "ATE-AI-Platform"
    VERSION: str = "0.2.0"
    DEBUG: bool = True

    # ========== 路径配置 ==========
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    RAW_DIR: Path = BASE_DIR / "data" / "raw"
    LOG_DIR: Path = BASE_DIR / "logs"

    # ========== PDF处理配置 ==========
    MAX_PAGES_PER_BATCH: int = 10
    MAX_TEXT_LENGTH: int = 6000

    # ========== 提取配置 ==========
    MAX_WORKERS: int = 5
    TEMPERATURE: float = 0
    MAX_TOKENS: int = 8192
    CONFIDENCE_THRESHOLD: float = 0.75

    # ========== STS8200S 机台配置 ==========
    STS8200S_VI_VOLTAGE_MAX: float = 10.0
    STS8200S_VI_CURRENT_MAX: float = 0.2
    STS8200S_DIO_CHANNELS: int = 24
    STS8200S_CBIT_CHANNELS: int = 40

    # ========== 前端跨域配置 ==========
    ALLOWED_ORIGINS: list = ["*"]
    CLEAR_PROXY_ENV: bool = False
    SSL_VERIFY: bool = True

    # ========== 芯片类型识别配置 ==========
    ENABLE_CHIP_TYPE_DETECTION: bool = True
    DEFAULT_CHIP_TYPE: str = "UNKNOWN"

    class Config:
        env_file = str(BASE_DIR / "backend" / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_value(cls, value):
        """Accept non-boolean debug-like env values (e.g. DEBUG=release)."""
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
        """创建必要的目录"""
        for dir_path in [
            self.UPLOAD_DIR,
            self.PROCESSED_DIR,
            self.RAW_DIR,
            self.LOG_DIR
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 导出BASE_DIR供其他模块使用
__all__ = ["Settings", "get_settings", "BASE_DIR"]


# 测试代码
if __name__ == "__main__":
    settings = get_settings()
    print("=" * 60)
    print("配置信息")
    print("=" * 60)
    print(f"项目名称: {settings.PROJECT_NAME}")
    print(f"版本: {settings.VERSION}")
    print(f"调试模式: {settings.DEBUG}")
    print(f"API密钥: {'已配置:' + settings.DEEPSEEK_API_KEY[:8] + '...' if settings.DEEPSEEK_API_KEY else '未配置'}")
    print(f"数据目录: {settings.DATA_DIR}")
    print(f"上传目录: {settings.UPLOAD_DIR}")
    print(f"处理目录: {settings.PROCESSED_DIR}")
    print(f"最大并发: {settings.MAX_WORKERS}")
    print(f".env路径: {BASE_DIR / 'backend' / '.env'}")
    print(f".env存在: {(BASE_DIR / 'backend' / '.env').exists()}")
    print("=" * 60)
    settings.create_dirs()
    print("✅ 必要目录已创建")
