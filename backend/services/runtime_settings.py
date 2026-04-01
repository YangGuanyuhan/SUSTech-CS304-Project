"""Runtime-only settings for sensitive integrations."""

from __future__ import annotations

from threading import Lock

from pydantic import BaseModel

from backend.config import get_settings


class RuntimeLLMConfig(BaseModel):
    """Public runtime LLM config returned to the UI."""

    provider: str
    model: str
    base_url: str | None = None
    api_key_configured: bool = False


class RuntimeLLMUpdate(BaseModel):
    """Writable runtime LLM config payload."""

    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    replace_api_key: bool = False


class RuntimeSettingsManager:
    """Keep sensitive runtime config in process memory only."""

    def __init__(self) -> None:
        settings = get_settings()
        self._provider = settings.llm_provider
        self._model = settings.llm_model
        self._base_url = settings.llm_base_url
        self._api_key = settings.llm_api_key if settings.llm_api_key != "replace-me" else None
        self._lock = Lock()

    def get_llm_config(self) -> RuntimeLLMConfig:
        """Return safe runtime config without exposing the secret."""

        with self._lock:
            return RuntimeLLMConfig(
                provider=self._provider,
                model=self._model,
                base_url=self._base_url,
                api_key_configured=bool(self._api_key),
            )

    def update_llm_config(self, update: RuntimeLLMUpdate) -> RuntimeLLMConfig:
        """Update runtime config. Empty api_key leaves the previous secret unchanged."""

        with self._lock:
            self._provider = update.provider.strip()
            self._model = update.model.strip()
            self._base_url = update.base_url.strip() if update.base_url else None
            if update.replace_api_key:
                self._api_key = update.api_key.strip() if update.api_key else None
            elif update.api_key:
                self._api_key = update.api_key.strip()
            return RuntimeLLMConfig(
                provider=self._provider,
                model=self._model,
                base_url=self._base_url,
                api_key_configured=bool(self._api_key),
            )

    def get_secret_api_key(self) -> str | None:
        """Return the in-memory API key for internal use only."""

        with self._lock:
            return self._api_key


runtime_settings = RuntimeSettingsManager()
