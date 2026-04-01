from backend.services.runtime_settings import RuntimeLLMUpdate, runtime_settings


def test_runtime_settings_masks_secret():
    runtime_settings.update_llm_config(
        RuntimeLLMUpdate(provider="openai", model="gpt-4o-mini", base_url=None, api_key="secret-1")
    )
    config = runtime_settings.get_llm_config()
    assert config.api_key_configured is True
    assert not hasattr(config, "api_key")


def test_runtime_settings_keeps_existing_secret_on_blank_update():
    runtime_settings.update_llm_config(
        RuntimeLLMUpdate(provider="openai", model="gpt-4o-mini", base_url=None, api_key="secret-2")
    )
    runtime_settings.update_llm_config(
        RuntimeLLMUpdate(provider="custom", model="demo-model", base_url="https://example.com/v1", api_key=None)
    )
    config = runtime_settings.get_llm_config()
    assert config.provider == "custom"
    assert config.model == "demo-model"
    assert config.base_url == "https://example.com/v1"
    assert runtime_settings.get_secret_api_key() == "secret-2"


def test_runtime_settings_can_clear_secret():
    runtime_settings.update_llm_config(
        RuntimeLLMUpdate(provider="openai", model="gpt-4o-mini", base_url=None, api_key="secret-3")
    )
    runtime_settings.update_llm_config(
        RuntimeLLMUpdate(
            provider="openai",
            model="gpt-4o-mini",
            base_url=None,
            api_key=None,
            replace_api_key=True,
        )
    )
    assert runtime_settings.get_secret_api_key() is None
