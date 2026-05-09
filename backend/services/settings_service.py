"""Persisted settings service."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.db.repositories import UserPreferenceRepository
from backend.models.settings import BlackboardProfile, EmailProfile, LLMProfile
from backend.services.runtime_settings import (
    RuntimeBlackboardUpdate,
    RuntimeEmailUpdate,
    RuntimeLLMUpdate,
    runtime_settings,
)
from backend.services.secret_store import secret_store

LLM_PROFILE_PREFIX = "llm_profile:"
LLM_PROFILE_SECRET_PREFIX = "llm_profile_secret:"
BB_PROFILE_PREFIX = "bb_profile:"
BB_PROFILE_SECRET_PREFIX = "bb_profile_secret:"
EMAIL_PROFILE_PREFIX = "email_profile:"
EMAIL_PROFILE_SECRET_PREFIX = "email_profile_secret:"


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
            payload["api_key_configured"] = (
                f"{LLM_PROFILE_SECRET_PREFIX}{payload['name']}" in secret_keys
            )
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
                "enable_reasoning": getattr(profile, "enable_reasoning", False),
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
        secret_record = next(
            (item for item in secret_records if item.key == f"{LLM_PROFILE_SECRET_PREFIX}{name}"),
            None,
        )
        api_key = secret_store.decrypt(secret_record.value) if secret_record else None
        config = runtime_settings.update_llm_config(
            RuntimeLLMUpdate(
                provider=profile.provider,
                model=profile.model,
                base_url=profile.base_url,
                api_key=api_key,
                replace_api_key=api_key is not None,
                enable_reasoning=profile.enable_reasoning,
            )
        )
        profile.provider = config.provider
        profile.model = config.model
        profile.base_url = config.base_url
        profile.api_key_configured = config.api_key_configured
        return profile

    # Blackboard profile methods
    async def list_bb_profiles(self) -> list[BlackboardProfile]:
        records = self.repository.list(key_prefix=BB_PROFILE_PREFIX)
        secret_records = self.repository.list(key_prefix=BB_PROFILE_SECRET_PREFIX)
        secret_keys = {item.key for item in secret_records}
        profiles = []
        for record in records:
            payload = json.loads(record.value)
            payload["name"] = record.key.removeprefix(BB_PROFILE_PREFIX)
            payload["password_configured"] = (
                f"{BB_PROFILE_SECRET_PREFIX}{payload['name']}" in secret_keys
            )
            profiles.append(BlackboardProfile.model_validate(payload))
        profiles.sort(key=lambda item: item.name.lower())
        return profiles

    async def save_bb_profile(
        self, profile: BlackboardProfile, password: str | None = None
    ) -> BlackboardProfile:
        key = f"{BB_PROFILE_PREFIX}{profile.name}"
        value = json.dumps(
            {
                "student_id": profile.student_id,
                "base_url": profile.base_url,
            },
            ensure_ascii=False,
        )
        self.repository.upsert(key=key, value=value)
        if password:
            self.repository.upsert(
                key=f"{BB_PROFILE_SECRET_PREFIX}{profile.name}",
                value=secret_store.encrypt(password),
            )
            profile.password_configured = True
        return profile

    async def delete_bb_profile(self, name: str) -> bool:
        deleted = self.repository.delete(key=f"{BB_PROFILE_PREFIX}{name}")
        self.repository.delete(key=f"{BB_PROFILE_SECRET_PREFIX}{name}")
        return deleted

    async def apply_bb_profile(self, name: str) -> BlackboardProfile | None:
        profiles = await self.list_bb_profiles()
        profile = next((item for item in profiles if item.name == name), None)
        if profile is None:
            return None

        secret_records = self.repository.list(key_prefix=BB_PROFILE_SECRET_PREFIX)
        secret_record = next(
            (item for item in secret_records if item.key == f"{BB_PROFILE_SECRET_PREFIX}{name}"),
            None,
        )
        password = secret_store.decrypt(secret_record.value) if secret_record else None
        config = runtime_settings.update_blackboard_config(
            RuntimeBlackboardUpdate(
                student_id=profile.student_id,
                base_url=profile.base_url,
                password=password,
                replace_password=password is not None,
            )
        )
        profile.student_id = config.student_id
        profile.base_url = config.base_url
        profile.password_configured = config.password_configured
        return profile

    # Email profile methods
    async def list_email_profiles(self) -> list[EmailProfile]:
        records = self.repository.list(key_prefix=EMAIL_PROFILE_PREFIX)
        secret_records = self.repository.list(key_prefix=EMAIL_PROFILE_SECRET_PREFIX)
        secret_keys = {item.key for item in secret_records}
        profiles = []
        for record in records:
            payload = json.loads(record.value)
            payload["name"] = record.key.removeprefix(EMAIL_PROFILE_PREFIX)
            payload["password_configured"] = (
                f"{EMAIL_PROFILE_SECRET_PREFIX}{payload['name']}" in secret_keys
            )
            profiles.append(EmailProfile.model_validate(payload))
        profiles.sort(key=lambda item: item.name.lower())
        return profiles

    async def save_email_profile(
        self, profile: EmailProfile, password: str | None = None
    ) -> EmailProfile:
        key = f"{EMAIL_PROFILE_PREFIX}{profile.name}"
        value = json.dumps(
            {
                "smtp_host": profile.smtp_host,
                "smtp_port": profile.smtp_port,
                "smtp_user": profile.smtp_user,
                "smtp_encryption": profile.smtp_encryption,
                "imap_host": profile.imap_host,
                "imap_port": profile.imap_port,
            },
            ensure_ascii=False,
        )
        self.repository.upsert(key=key, value=value)
        if password:
            self.repository.upsert(
                key=f"{EMAIL_PROFILE_SECRET_PREFIX}{profile.name}",
                value=secret_store.encrypt(password),
            )
            profile.password_configured = True
        return profile

    async def delete_email_profile(self, name: str) -> bool:
        deleted = self.repository.delete(key=f"{EMAIL_PROFILE_PREFIX}{name}")
        self.repository.delete(key=f"{EMAIL_PROFILE_SECRET_PREFIX}{name}")
        return deleted

    async def apply_email_profile(self, name: str) -> EmailProfile | None:
        profiles = await self.list_email_profiles()
        profile = next((item for item in profiles if item.name == name), None)
        if profile is None:
            return None

        secret_records = self.repository.list(key_prefix=EMAIL_PROFILE_SECRET_PREFIX)
        secret_record = next(
            (item for item in secret_records if item.key == f"{EMAIL_PROFILE_SECRET_PREFIX}{name}"),
            None,
        )
        password = secret_store.decrypt(secret_record.value) if secret_record else None
        config = runtime_settings.update_email_config(
            RuntimeEmailUpdate(
                smtp_host=profile.smtp_host,
                smtp_port=profile.smtp_port,
                smtp_user=profile.smtp_user,
                smtp_encryption=profile.smtp_encryption,
                imap_host=profile.imap_host,
                imap_port=profile.imap_port,
                password=password,
                replace_password=password is not None,
            )
        )
        profile.smtp_host = config.smtp_host
        profile.smtp_port = config.smtp_port
        profile.smtp_user = config.smtp_user
        profile.smtp_encryption = config.smtp_encryption
        profile.imap_host = config.imap_host
        profile.imap_port = config.imap_port
        profile.password_configured = config.password_configured
        return profile
