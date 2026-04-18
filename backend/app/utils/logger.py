"""
日志工具
"""
from loguru import logger
import sys
from pathlib import Path
from app.core.config import get_settings

settings = get_settings()


def setup_logger(log_file: str = "extraction.log"):
    """配置日志系统"""

    # 移除默认handler
    logger.remove()

    # 控制台输出（彩色）
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True
    )

    # 文件输出（详细）
    log_path = settings.LOG_DIR / log_file
    logger.add(
        str(log_path),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",  # 10MB后轮转
        retention="7 days",  # 保留7天
        compression="zip",  # 压缩旧日志
        encoding="utf-8"
    )

    # 错误单独记录
    error_log_path = settings.LOG_DIR / "error.log"
    logger.add(
        str(error_log_path),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="10 MB",
        encoding="utf-8"
    )

    return logger


# 测试
if __name__ == "__main__":
    log = setup_logger()
    log.info("这是一条信息日志")
    log.warning("这是一条警告日志")
    log.error("这是一条错误日志")
    log.success("这是一条成功日志")