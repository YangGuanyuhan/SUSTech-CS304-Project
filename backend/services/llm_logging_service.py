"""Structured logging for LLM request and response turns."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.config import get_settings

_INVALID_SESSION_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")


def _truncate_text(value: str | None, limit: int = 3000) -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return value[:limit] + "...<truncated>"


class LLMLoggingService:
    """Write compact JSONL logs grouped by session id."""

    def __init__(self, log_dir: str | None = None) -> None:
        settings = get_settings()
        self.log_dir = Path(log_dir or settings.llm_log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "event_type": event_type,
            "payload": payload,
        }
        path = self._log_path(session_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def summarize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summary: list[dict[str, Any]] = []
        for message in messages:
            entry: dict[str, Any] = {"role": message.get("role", "unknown")}
            if "content" in message:
                entry["content"] = _truncate_text(str(message.get("content") or ""))
            if "tool_calls" in message:
                entry["tool_calls"] = [
                    {
                        "id": item.get("id"),
                        "name": item.get("function", {}).get("name"),
                        "arguments": _truncate_text(
                            item.get("function", {}).get("arguments", ""), limit=1200
                        ),
                    }
                    for item in message.get("tool_calls", [])
                ]
            if "tool_call_id" in message:
                entry["tool_call_id"] = message.get("tool_call_id")
            summary.append(entry)
        return summary

    def summarize_response(self, response: Any) -> dict[str, Any]:
        choice = response.choices[0]
        message = choice.message
        return {
            "finish_reason": getattr(choice, "finish_reason", None),
            "content": _truncate_text(message.content or ""),
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": _truncate_text(tool_call.function.arguments or "", limit=1200),
                }
                for tool_call in (message.tool_calls or [])
            ],
        }

    def _log_path(self, session_id: str) -> Path:
        safe_session_id = _INVALID_SESSION_CHARS.sub("_", session_id).strip("._") or "default"
        return self.log_dir / f"{safe_session_id}.jsonl"


llm_logger = LLMLoggingService()
