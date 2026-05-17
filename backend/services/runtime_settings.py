"""Runtime-only settings for sensitive integrations."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from pydantic import BaseModel

from backend.config import get_settings
from backend.services.secret_store import secret_store

# Secret prefix for encrypted storage (shared with settings_service to avoid circular import)
SECRET_PREFIX = "llm_profile_secret:"


class RuntimeLLMConfig(BaseModel):
    """Public runtime LLM config returned to the UI."""

    provider: str
    model: str
    base_url: str | None = None
    api_key_configured: bool = False
    enable_reasoning: bool = False


class RuntimeLLMUpdate(BaseModel):
    """Writable runtime LLM config payload."""

    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    replace_api_key: bool = False
    enable_reasoning: bool = False


class RuntimeBlackboardConfig(BaseModel):
    """Public runtime Blackboard config without exposing password."""

    student_id: str | None = None
    base_url: str | None = None
    password_configured: bool = False


class RuntimeBlackboardUpdate(BaseModel):
    """Writable runtime Blackboard config payload."""

    student_id: str | None = None
    password: str | None = None
    base_url: str | None = None
    replace_password: bool = False


class RuntimeEmailConfig(BaseModel):
    """Public runtime Email config without exposing password."""

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_encryption: str = "ssl"
    imap_host: str
    imap_port: int
    password_configured: bool = False


class RuntimeEmailUpdate(BaseModel):
    """Writable runtime Email config payload."""

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_encryption: str = "ssl"
    imap_host: str
    imap_port: int
    password: str | None = None
    replace_password: bool = False


class RuntimeSearchConfig(BaseModel):
    """Public runtime search config without exposing provider secrets."""

    provider: str
    api_key_configured: bool = False
    timeout: int


class RuntimeSearchUpdate(BaseModel):
    """Writable runtime search config payload."""

    provider: str
    api_key: str | None = None
    replace_api_key: bool = False
    timeout: int | None = None


class RuntimeSettingsManager:
    """Keep sensitive runtime config in process memory only."""

    def __init__(self) -> None:
        settings = get_settings()
        self._provider = settings.llm_provider
        self._model = settings.llm_model
        self._base_url = settings.llm_base_url
        self._api_key = settings.llm_api_key if settings.llm_api_key != "replace-me" else None
        self._enable_reasoning = settings.llm_enable_reasoning
        # Blackboard config - load encrypted password from settings, file, or environment
        self._bb_student_id = settings.blackboard_student_id
        # Priority: env var > encrypted file > none
        self._bb_password = (
            self._load_blackboard_password(settings.blackboard_cas_password)
            or self._load_encrypted_password_from_file()
        )
        self._bb_base_url = settings.blackboard_base_url
        # Email config
        self._smtp_host = settings.smtp_host
        self._smtp_port = settings.smtp_port
        self._smtp_user = settings.smtp_user
        self._smtp_encryption = settings.smtp_encryption
        self._smtp_password = (
            settings.smtp_password if settings.smtp_password != "replace-me" else None
        )
        self._imap_host = settings.imap_host
        self._imap_port = settings.imap_port
        # Search config
        self._search_provider = settings.search_provider
        self._search_timeout = settings.search_timeout
        self._search_api_keys = {
            "brave": settings.brave_api_key,
            "bocha": settings.bocha_api_key,
            "tavily": settings.tavily_api_key,
        }
        self._lock = Lock()

    def _load_blackboard_password(self, stored_password: str | None) -> str | None:
        """Load password, trying to decrypt if it was stored encrypted."""
        if not stored_password:
            return None
        # Check if it's encrypted (starts with encrypted prefix)
        if stored_password.startswith(SECRET_PREFIX):
            try:
                return secret_store.decrypt(stored_password[len(SECRET_PREFIX) :])
            except Exception:
                return None
        # Otherwise return as-is (from environment variable)
        return stored_password

    def get_llm_config(self) -> RuntimeLLMConfig:
        """Return safe runtime config without exposing the secret."""

        with self._lock:
            return RuntimeLLMConfig(
                provider=self._provider,
                model=self._model,
                base_url=self._base_url,
                api_key_configured=bool(self._api_key),
                enable_reasoning=self._enable_reasoning,
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
            self._enable_reasoning = update.enable_reasoning
            return RuntimeLLMConfig(
                provider=self._provider,
                model=self._model,
                base_url=self._base_url,
                api_key_configured=bool(self._api_key),
                enable_reasoning=self._enable_reasoning,
            )

    def get_secret_api_key(self) -> str | None:
        """Return the in-memory API key for internal use only."""

        with self._lock:
            return self._api_key

    # Blackboard config methods
    def get_blackboard_config(self) -> RuntimeBlackboardConfig:
        """Return safe runtime Blackboard config without exposing password."""

        with self._lock:
            return RuntimeBlackboardConfig(
                student_id=self._bb_student_id,
                base_url=self._bb_base_url,
                password_configured=bool(self._bb_password),
            )

    def _save_encrypted_password(self, password: str | None) -> None:
        """Save encrypted password to local file."""

        secrets_dir = Path("data")
        secrets_dir.mkdir(parents=True, exist_ok=True)
        secrets_file = secrets_dir / "blackboard-secrets.json"

        if password:
            encrypted = f"{SECRET_PREFIX}{secret_store.encrypt(password)}"
            import json

            secrets_file.write_text(json.dumps({"password": encrypted}))
        elif secrets_file.exists():
            secrets_file.unlink()

    def _load_encrypted_password_from_file(self) -> str | None:
        """Load encrypted password from local file."""

        secrets_file = Path("data/blackboard-secrets.json")
        if secrets_file.exists():
            try:
                import json

                data = json.loads(secrets_file.read_text())
                stored = data.get("password", "")
                if stored.startswith(SECRET_PREFIX):
                    return secret_store.decrypt(stored[len(SECRET_PREFIX) :])
            except Exception:
                pass
        return None

    def update_blackboard_config(self, update: RuntimeBlackboardUpdate) -> RuntimeBlackboardConfig:
        """Update runtime Blackboard config. Empty password leaves the previous unchanged."""

        with self._lock:
            if update.student_id:
                self._bb_student_id = update.student_id.strip()
            if update.replace_password:
                self._bb_password = update.password.strip() if update.password else None
                self._save_encrypted_password(self._bb_password)
            elif update.password:
                self._bb_password = update.password.strip()
                self._save_encrypted_password(self._bb_password)
            if update.base_url:
                self._bb_base_url = update.base_url.strip()
            return RuntimeBlackboardConfig(
                student_id=self._bb_student_id,
                base_url=self._bb_base_url,
                password_configured=bool(self._bb_password),
            )

    def get_secret_blackboard_password(self) -> str | None:
        """Return the in-memory Blackboard password for internal use only."""

        with self._lock:
            return self._bb_password

    # Email config methods
    def get_email_config(self) -> RuntimeEmailConfig:
        """Return safe runtime Email config without exposing password."""

        with self._lock:
            return RuntimeEmailConfig(
                smtp_host=self._smtp_host,
                smtp_port=self._smtp_port,
                smtp_user=self._smtp_user,
                smtp_encryption=self._smtp_encryption,
                imap_host=self._imap_host,
                imap_port=self._imap_port,
                password_configured=bool(self._smtp_password),
            )

    def update_email_config(self, update: RuntimeEmailUpdate) -> RuntimeEmailConfig:
        """Update runtime Email config."""

        with self._lock:
            self._smtp_host = update.smtp_host.strip()
            self._smtp_port = update.smtp_port
            self._smtp_user = update.smtp_user.strip()
            self._smtp_encryption = update.smtp_encryption.strip()
            self._imap_host = update.imap_host.strip()
            self._imap_port = update.imap_port
            if update.replace_password:
                self._smtp_password = update.password.strip() if update.password else None
            elif update.password:
                self._smtp_password = update.password.strip()
            return RuntimeEmailConfig(
                smtp_host=self._smtp_host,
                smtp_port=self._smtp_port,
                smtp_user=self._smtp_user,
                smtp_encryption=self._smtp_encryption,
                imap_host=self._imap_host,
                imap_port=self._imap_port,
                password_configured=bool(self._smtp_password),
            )

    def get_secret_email_password(self) -> str | None:
        """Return the in-memory Email password for internal use only."""

        with self._lock:
            return self._smtp_password

    # Search config methods
    def get_search_config(self) -> RuntimeSearchConfig:
        """Return safe runtime search config without exposing API keys."""

        with self._lock:
            provider = self._search_provider.strip().lower()
            return RuntimeSearchConfig(
                provider=provider,
                api_key_configured=bool(self._search_api_keys.get(provider)) or provider == "mock",
                timeout=self._search_timeout,
            )

    def update_search_config(self, update: RuntimeSearchUpdate) -> RuntimeSearchConfig:
        """Update runtime search config. Empty api_key leaves the previous secret unchanged."""

        with self._lock:
            provider = update.provider.strip().lower()
            self._search_provider = provider
            if update.timeout is not None:
                self._search_timeout = update.timeout
            if update.replace_api_key:
                self._search_api_keys[provider] = update.api_key.strip() if update.api_key else None
            elif update.api_key:
                self._search_api_keys[provider] = update.api_key.strip()
            return RuntimeSearchConfig(
                provider=provider,
                api_key_configured=bool(self._search_api_keys.get(provider)) or provider == "mock",
                timeout=self._search_timeout,
            )

    def get_secret_search_api_key(self, provider: str | None = None) -> str | None:
        """Return the in-memory search API key for internal use only."""

        with self._lock:
            resolved_provider = (provider or self._search_provider).strip().lower()
            return self._search_api_keys.get(resolved_provider)

    def get_search_timeout(self) -> int:
        """Return the runtime search timeout."""

        with self._lock:
            return self._search_timeout


runtime_settings = RuntimeSettingsManager()
