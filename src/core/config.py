"""
ИИ-Корпорация 2.0 — Центральная конфигурация
"""
from pydantic_settings import BaseSettings
from typing import Optional
import enum


class ModelTier(str, enum.Enum):
    LOCAL_SMALL = "local_small"
    LOCAL_MEDIUM = "local_medium"
    LOCAL_LARGE = "local_large"
    CLOUD_CLAUDE = "cloud_claude"
    CLOUD_OPENAI = "cloud_openai"


class Priority(int, enum.Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class Settings(BaseSettings):
    """Настройки приложения из .env файла"""

    # Telegram
    telegram_bot_token: str = "not_set"
    telegram_admin_id: int = 0

    # API Keys
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "qwen2.5:14b"

    # GPU
    gpu_total_vram_gb: float = 24.0
    gpu_reserved_vram_gb: float = 2.0
    gpu_max_models_loaded: int = 2

    # Task Queue
    max_concurrent_tasks: int = 3
    task_timeout_seconds: int = 600
    max_retries: int = 3

    # Database
    database_url: str = "postgresql+asyncpg://ai_corp:password@localhost:5432/ai_corporation"
    redis_url: str = "redis://localhost:6379/0"

    # Security
    jwt_secret_key: str = "change-me-in-production"
    rate_limit_per_minute: int = 50
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Paths
    models_cache_dir: str = "/opt/ai-corp/models"
    output_dir: str = "/opt/ai-corp/output"
    logs_dir: str = "/opt/ai-corp/logs"

    class Config:
        env_file = ".env"
        env_prefix = "AI_CORP_"


settings = Settings()
