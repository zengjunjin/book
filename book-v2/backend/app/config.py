from pydantic_settings import BaseSettings
from typing import Optional
import secrets
import os


class Settings(BaseSettings):
    """应用配置"""

    USE_SQLITE: bool = os.getenv("USE_SQLITE", "0") == "1"
    _default_db = "sqlite:///./book_recommend.db" if USE_SQLITE else "postgresql://postgres:postgres123@localhost:5432/book_recommend?client_encoding=utf8"
    DATABASE_URL: str = os.getenv("DATABASE_URL", _default_db)

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # 安全 - SECRET_KEY 必须从环境变量读取，生产环境必须设置
    SECRET_KEY: str = secrets.token_urlsafe(32)  # 默认生成随机值，但生产环境应该从环境变量读取
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 应用
    DEBUG: bool = True
    APP_NAME: str = "Book Recommendation API"
    VERSION: str = "2.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
