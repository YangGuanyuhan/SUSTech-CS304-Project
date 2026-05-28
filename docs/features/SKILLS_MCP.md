# Skills And MCP

StudyAI supports two extension paths for the agent:

- Skills: reusable workflow instructions stored as local `SKILL.md` files.
- MCP servers: external tool providers connected at runtime through Model Context Protocol.

Both are configured from the Settings panel and are surfaced to the PydanticAI runtime before each chat turn.

## Skills

Skills follow the Codex-style skill layout. A skill is a directory with a required `SKILL.md` file:

```text
.agents/skills/my-skill/
├── SKILL.md
├── scripts/
├── references/
└── agents/
    └── openai.yaml
```

`SKILL.md` must start with YAML frontmatter:

```md
---
name: my-skill
description: Use this when the agent should follow this specific workflow.
---

Follow these steps when the skill is selected.
```

The backend discovers skills from:

- `.agents/skills` in the current repository path chain
- `.agents/skills` in the active workspace path chain, when a workspace root is supplied
- `~/.agents/skills`

The Settings panel shows each skill's name, description, scope, path, and invocation mode.

### Invocation Behavior

The agent receives a compact list of enabled skill metadata in its dynamic system prompt. It should call `read_skill` before following the full `SKILL.md` body.

Available skill tools:

- `list_skills`: list discovered skill metadata
- `read_skill`: read the selected skill's `SKILL.md`
- `read_skill_resource`: read a file inside the selected skill directory

If `agents/openai.yaml` contains:

```yaml
policy:
  allow_implicit_invocation: false
```

the skill remains visible, but the agent is instructed to use it only when explicitly requested.

## MCP Servers

MCP servers are configured in `Settings > MCP`. The UI supports:

- `stdio`
- `streamable_http`
- `sse`

Each server has:

- `Server ID`: stable identifier, letters/numbers/`_`/`-` only
- `Transport`: connection type
- `Tool prefix`: optional prefix for tools exposed by the MCP server
- `Command` and `Args`: for `stdio`
- `URL`: for `streamable_http` and `sse`
- key-value environment variables or HTTP headers

Example HTTP header:

```text
Authorization = Bearer <token>
```

Example stdio environment variable:

```text
MCP_API_KEY = <token>
```

Use the `Test` button to start the server and list available tools. A successful test returns the number of discovered tools and the prefixed names that the agent can call.

## Persistence And Secrets

MCP configuration is persisted in:

```text
data/mcp-settings.json
```

Secret-bearing fields are encrypted before writing to disk:

- HTTP/SSE `headers`
- stdio `env`

When configuration is returned to the browser, secret values are masked as:

```text
********
```

If the user edits a server and keeps a masked value unchanged, the backend preserves the previous encrypted secret. Test calls and runtime agent calls resolve masked values back to the stored secret on the backend side.

## Runtime Behavior

Enabled MCP servers are attached to the PydanticAI agent as MCP toolsets. The agent prompt includes a compact list of enabled servers and their tool prefixes.

MCP tool calls are tracked like built-in tools:

- running/completed/failed tool events are streamed to the chat UI
- used MCP tools are included in the runtime `tools_used` list
- startup failures are logged and the agent falls back to built-in tools for that turn

For HTTP/SSE MCP servers, the backend creates an HTTP client with `trust_env=False`. This prevents environment proxy variables such as `HTTP_PROXY`, `HTTPS_PROXY`, or `ALL_PROXY` from intercepting MCP traffic.

## API Endpoints

Skills:

- `GET /api/settings/skills`
- `POST /api/settings/skills/refresh`

MCP:

- `GET /api/settings/mcp`
- `PUT /api/settings/mcp`
- `POST /api/settings/mcp/test`

## Main Implementation Files

- `backend/services/skill_service.py`
- `backend/services/mcp_service.py`
- `backend/services/runtime_settings.py`
- `backend/services/agent_tool_service.py`
- `backend/agent/pydantic_runtime.py`
- `frontend/src/components/SettingsPanel.vue`
