from backend.models.settings import LLMProfile
from backend.services.settings_service import SettingsService


async def test_save_and_list_llm_profiles(db_session):
    service = SettingsService(db_session)
    await service.save_llm_profile(
        LLMProfile(
            name="openai-main",
            provider="openai",
            model="gpt-4.1-mini",
            base_url="https://api.openai.com/v1",
        ),
        api_key="secret-key",
    )
    profiles = await service.list_llm_profiles()
    assert len(profiles) == 1
    assert profiles[0].name == "openai-main"
    assert profiles[0].api_key_configured is True


async def test_delete_llm_profile(db_session):
    service = SettingsService(db_session)
    await service.save_llm_profile(
        LLMProfile(
            name="gateway-a",
            provider="openai",
            model="gpt-4o-mini",
            base_url="https://example.com/v1",
        )
    )
    deleted = await service.delete_llm_profile("gateway-a")
    profiles = await service.list_llm_profiles()
    assert deleted is True
    assert profiles == []


async def test_apply_profile_updates_runtime_config(db_session):
    service = SettingsService(db_session)
    await service.save_llm_profile(
        LLMProfile(
            name="dashscope",
            provider="openai",
            model="qwen3.5-plus",
            base_url="https://coding.dashscope.aliyuncs.com/v1",
        ),
        api_key="secret-dashscope",
    )
    applied = await service.apply_llm_profile("dashscope")
    assert applied is not None
    assert applied.model == "qwen3.5-plus"
    assert applied.api_key_configured is True
