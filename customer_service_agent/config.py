"""Runtime configuration for the enterprise customer service platform."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CUSTOMER_SERVICE_", extra="ignore")

    app_name: str = "Enterprise Intelligent Customer Service"
    environment: str = "dev"
    db_url: str = "postgresql+psycopg://customer_service:customer_service_pass@postgres:5432/customer_service"
    redis_url: str = "redis://redis:6379/0"
    auto_init_db: bool = True
    seed_demo_data: bool = True
    fake_llm: bool = False

    llm_provider: str = Field(default="qwen", description="qwen, deepseek, openai-compatible")
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_temperature: float = 0.2

    embedding_provider: str = "dashscope-compatible"
    embedding_model: str = "text-embedding-v3"
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_api_key: str = ""
    embedding_dimension: int = 1024

    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    cache_max_size: int = 512
    conversation_window: int = 12


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
