"""Helpers for runtime MCP server configuration."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio, MCPServerStreamableHTTP

from backend.services.runtime_settings import RuntimeMCPServerConfig

MCPServerInstance = MCPServerStdio | MCPServerStreamableHTTP | MCPServerSSE


def build_mcp_prompt(servers: list[RuntimeMCPServerConfig]) -> str:
    """Describe enabled MCP servers for the agent prompt."""

    enabled = [server for server in servers if server.enabled]
    if not enabled:
        return "No MCP servers are currently enabled."
    lines = [
        "Enabled MCP servers:",
        "Use MCP tools when they directly match the user's request. MCP tools are exposed with the listed prefix.",
    ]
    for server in enabled:
        endpoint = server.command if server.transport == "stdio" else server.url
        lines.append(
            f"- {server.id}: transport={server.transport}, tool_prefix={server.tool_prefix or server.id}, endpoint={endpoint or 'configured'}"
        )
    return "\n".join(lines)


def build_mcp_server(
    config: RuntimeMCPServerConfig,
    *,
    process_tool_call: Any = None,
) -> MCPServerInstance:
    """Build a PydanticAI MCP server from runtime config."""

    tool_prefix = config.tool_prefix or config.id
    if config.transport == "stdio":
        return MCPServerStdio(
            command=config.command or "",
            args=config.args,
            env=config.env or None,
            cwd=config.cwd,
            tool_prefix=tool_prefix,
            timeout=config.timeout,
            read_timeout=config.read_timeout,
            process_tool_call=process_tool_call,
            id=config.id,
        )
    if config.transport == "streamable_http":
        return MCPServerStreamableHTTP(
            url=config.url or "",
            http_client=httpx.AsyncClient(
                headers=config.headers or None,
                timeout=httpx.Timeout(config.timeout, read=config.read_timeout),
                trust_env=False,
            ),
            tool_prefix=tool_prefix,
            timeout=config.timeout,
            read_timeout=config.read_timeout,
            process_tool_call=process_tool_call,
            id=config.id,
        )
    return MCPServerSSE(
        url=config.url or "",
        http_client=httpx.AsyncClient(
            headers=config.headers or None,
            timeout=httpx.Timeout(config.timeout, read=config.read_timeout),
            trust_env=False,
        ),
        tool_prefix=tool_prefix,
        timeout=config.timeout,
        read_timeout=config.read_timeout,
        process_tool_call=process_tool_call,
        id=config.id,
    )


async def test_mcp_server(config: RuntimeMCPServerConfig) -> dict[str, Any]:
    """Start a server and list its tools."""

    server = build_mcp_server(config)
    tools = await server.list_tools()
    return {
        "ok": True,
        "id": config.id,
        "transport": config.transport,
        "tool_count": len(tools),
        "tools": [f"{config.tool_prefix or config.id}_{tool.name}" for tool in tools],
    }
