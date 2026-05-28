import json
from pathlib import Path

import pytest

from backend.agent.pydantic_runtime import PydanticAIRuntime
from backend.services.agent_tool_service import AgentToolService, ToolExecutionError
from backend.services.mcp_service import build_mcp_prompt
from backend.services.runtime_settings import (
    MASKED_SECRET,
    RuntimeMCPServerConfig,
    RuntimeMCPUpdate,
    RuntimeSettingsManager,
)
from backend.services.skill_service import SkillService, SkillServiceError


def _write_skill(root: Path, name: str, description: str = "Handle demo tasks.") -> Path:
    skill_dir = root / ".agents" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nFollow demo instructions.\n",
        encoding="utf-8",
    )
    return skill_dir


def test_skill_service_discovers_valid_workspace_skill(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    skill_dir = _write_skill(tmp_path, "demo-skill")
    (skill_dir / "agents").mkdir()
    (skill_dir / "agents" / "openai.yaml").write_text(
        "policy:\n  allow_implicit_invocation: false\n",
        encoding="utf-8",
    )

    skills = SkillService(str(tmp_path)).discover()

    skill = next(item for item in skills if item.name == "demo-skill")
    assert skill.enabled is True
    assert skill.allow_implicit_invocation is False
    assert skill.has_openai_metadata is True


def test_skill_service_marks_invalid_skill_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    skill_dir = tmp_path / ".agents" / "skills" / "bad-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# missing frontmatter\n", encoding="utf-8")

    skills = SkillService(str(tmp_path)).discover()

    skill = next(item for item in skills if item.name == "bad-skill")
    assert skill.enabled is False
    assert "frontmatter" in (skill.error or "")


def test_skill_service_reads_skill_and_blocks_resource_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _write_skill(tmp_path, "demo-skill")
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    service = SkillService(str(tmp_path))

    result = service.read_skill("demo-skill")

    assert "Follow demo instructions" in result.content
    with pytest.raises(SkillServiceError):
        service.read_resource("demo-skill", "../../outside.txt")


async def test_agent_tool_service_exposes_skill_tools(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _write_skill(tmp_path, "demo-skill")
    service = AgentToolService(db_session)

    listed_raw = await service.execute(
        "list_skills",
        {},
        chat_session_id="chat-1",
        workspace_root=str(tmp_path),
    )
    listed = json.loads(listed_raw)
    assert any(skill["name"] == "demo-skill" for skill in listed["skills"])

    read_raw = await service.execute(
        "read_skill",
        {"name": "demo-skill"},
        chat_session_id="chat-1",
        workspace_root=str(tmp_path),
    )
    assert "Follow demo instructions" in json.loads(read_raw)["content"]

    with pytest.raises(ToolExecutionError):
        await service.execute(
            "read_skill_resource",
            {"name": "demo-skill", "path": "../../outside.txt"},
            chat_session_id="chat-1",
            workspace_root=str(tmp_path),
        )


def test_runtime_mcp_config_validation_and_toolset_build(db_session):
    from backend.services.runtime_settings import runtime_settings

    try:
        config = RuntimeMCPServerConfig(
            id="demo",
            transport="stdio",
            command="python",
            args=["-m", "demo"],
            tool_prefix="demo",
        )
        updated = runtime_settings.update_mcp_config(RuntimeMCPUpdate(servers=[config]))

        assert updated.servers[0].id == "demo"
        toolsets = PydanticAIRuntime(db_session)._build_mcp_toolsets()
        assert len(toolsets) == 1
        assert toolsets[0].tool_prefix == "demo"
    finally:
        runtime_settings.update_mcp_config(RuntimeMCPUpdate(servers=[]))


def test_runtime_mcp_config_rejects_missing_required_transport_fields():
    with pytest.raises(ValueError):
        RuntimeMCPServerConfig(id="bad", transport="stdio")
    with pytest.raises(ValueError):
        RuntimeMCPServerConfig(id="bad-http", transport="streamable_http")


def test_mcp_prompt_lists_enabled_servers_only():
    prompt = build_mcp_prompt(
        [
            RuntimeMCPServerConfig(id="food", transport="streamable_http", url="http://mcp.local"),
            RuntimeMCPServerConfig(
                id="disabled",
                enabled=False,
                transport="stdio",
                command="python",
            ),
        ]
    )

    assert "food" in prompt
    assert "tool_prefix=food" in prompt
    assert "disabled" not in prompt


def test_mcp_runtime_masks_and_preserves_secrets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = RuntimeSettingsManager()
    config = RuntimeMCPServerConfig(
        id="food",
        transport="streamable_http",
        url="http://mcp.local",
        headers={"Authorization": "Bearer secret-token"},
    )

    public = manager.update_mcp_config(RuntimeMCPUpdate(servers=[config]))

    assert public.servers[0].headers["Authorization"] == MASKED_SECRET
    assert manager.get_mcp_config().servers[0].headers["Authorization"] == "Bearer secret-token"
    raw_file = (tmp_path / "data" / "mcp-settings.json").read_text(encoding="utf-8")
    assert "Bearer secret-token" not in raw_file
    assert "mcp_secret:" in raw_file

    masked_update = RuntimeMCPServerConfig(
        id="food",
        transport="streamable_http",
        url="http://mcp.local",
        headers={"Authorization": MASKED_SECRET},
    )
    manager.update_mcp_config(RuntimeMCPUpdate(servers=[masked_update]))
    assert manager.get_mcp_config().servers[0].headers["Authorization"] == "Bearer secret-token"

    reloaded = RuntimeSettingsManager()
    assert reloaded.get_mcp_config().servers[0].headers["Authorization"] == "Bearer secret-token"
