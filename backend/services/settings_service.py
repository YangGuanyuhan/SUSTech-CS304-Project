"""Persisted settings service."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.db.repositories import UserPreferenceRepository
from backend.models.settings import LLMProfile
from backend.services.runtime_settings import RuntimeLLMUpdate, runtime_settings
from backend.services.secret_store import secret_store


LLM_PROFILE_PREFIX = "llm_profile:"
LLM_PROFILE_SECRET_PREFIX = "llm_profile_secret:"


class SettingsService:
    """Manage persisted non-secret settings."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = UserPreferenceRepository(session)

    async def list_llm_profiles(self) -> list[LLMProfile]:
        records = self.repository.list(key_prefix=LLM_PROFILE_PREFIX)
        secret_records = self.repository.list(key_prefix=LLM_PROFILE_SECRET_PREFIX)
        secret_keys = {item.key for item in secret_records}
        profiles = []
        for record in records:
            payload = json.loads(record.value)
            payload["name"] = record.key.removeprefix(LLM_PROFILE_PREFIX)
            payload["api_key_configured"] = f"{LLM_PROFILE_SECRET_PREFIX}{payload['name']}" in secret_keys
            profiles.append(LLMProfile.model_validate(payload))
        profiles.sort(key=lambda item: item.name.lower())
        return profiles

    async def save_llm_profile(self, profile: LLMProfile, api_key: str | None = None) -> LLMProfile:
        key = f"{LLM_PROFILE_PREFIX}{profile.name}"
        value = json.dumps(
            {
                "provider": profile.provider,
                "model": profile.model,
                "base_url": profile.base_url,
            },
            ensure_ascii=False,
        )
        self.repository.upsert(key=key, value=value)
        if api_key:
            self.repository.upsert(
                key=f"{LLM_PROFILE_SECRET_PREFIX}{profile.name}",
                value=secret_store.encrypt(api_key),
            )
            profile.api_key_configured = True
        return profile

    async def delete_llm_profile(self, name: str) -> bool:
        deleted = self.repository.delete(key=f"{LLM_PROFILE_PREFIX}{name}")
        self.repository.delete(key=f"{LLM_PROFILE_SECRET_PREFIX}{name}")
        return deleted

    async def apply_llm_profile(self, name: str) -> LLMProfile | None:
        profiles = await self.list_llm_profiles()
        profile = next((item for item in profiles if item.name == name), None)
        if profile is None:
            return None

        secret_records = self.repository.list(key_prefix=LLM_PROFILE_SECRET_PREFIX)
        secret_record = next((item for item in secret_records if item.key == f"{LLM_PROFILE_SECRET_PREFIX}{name}"), None)
        api_key = secret_store.decrypt(secret_record.value) if secret_record else None
        config = runtime_settings.update_llm_config(
            RuntimeLLMUpdate(
                provider=profile.provider,
                model=profile.model,
                base_url=profile.base_url,
                api_key=api_key,
                replace_api_key=api_key is not None,
            )
        )
        profile.provider = config.provider
        profile.model = config.model
        profile.base_url = config.base_url
        profile.api_key_configured = config.api_key_configured
        return profile
