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
    llm_enable_reasoning: bool = True

    blackboard_student_id: str | None = None
    blackboard_cas_password: str | None = None
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
    quiz_subjective_grading_timeout: int = 30
    llm_log_dir: str = "./data/llm-logs"
    rag_provider: str = "raganything"
    rag_storage_dir: str = "./data/rag"
    rag_allowed_extensions: list[str] = Field(
        default_factory=lambda: [".md", ".txt", ".pdf", ".docx", ".pptx", ".doc", ".ppt"]
    )
    rag_embedding_model: str = "text-embedding-3-small"
    rag_embedding_dim: int = 1536
    rag_chunk_size: int = 1200
    rag_top_k: int = 5
    rag_index_timeout_seconds: int = 180
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
