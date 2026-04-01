"""Application configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from the environment."""

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = "replace-me"
    llm_base_url: str | None = None

    blackboard_provider: str = "mock"
    blackboard_base_url: str = "https://bb.sustech.edu.cn/learn/api/public/v1"
    blackboard_token: str = "replace-me"

    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = "student@example.com"
    smtp_password: str = "replace-me"
    imap_host: str = "imap.example.com"

    search_provider: str = "mock"
    brave_api_key: str | None = None
    tavily_api_key: str | None = None

    database_url: str = "sqlite+aiosqlite:///./data/agent.db"
    search_timeout: int = 30
    api_timeout: int = 60
    task_timeout: int = 120
    llm_log_dir: str = "./data/llm-logs"
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
