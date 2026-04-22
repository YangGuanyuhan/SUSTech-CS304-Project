"""Helpers for extracting structured thinking/final sections from model output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

MAX_THINKING_LENGTH = 4000
THINKING_TRUNCATION_SUFFIX = "\n...(推理过程已截断)"

_THINKING_PATTERN = re.compile(r"<thinking>(.*?)</thinking>", re.IGNORECASE | re.DOTALL)
_FINAL_PATTERN = re.compile(r"<final>(.*?)</final>", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class ThinkingParseResult:
    thinking: str | None
    final_answer: str
    raw: str


def _clean_section(text: str) -> str:
    return text.strip()


def _truncate_thinking(text: str | None) -> str | None:
    if not text:
        return None
    if len(text) <= MAX_THINKING_LENGTH:
        return text
    limit = MAX_THINKING_LENGTH - len(THINKING_TRUNCATION_SUFFIX)
    if limit <= 0:
        return THINKING_TRUNCATION_SUFFIX.lstrip()
    return text[:limit].rstrip() + THINKING_TRUNCATION_SUFFIX


def _has_unbalanced_tag(text: str, tag_name: str) -> bool:
    opening = len(re.findall(rf"<{tag_name}>", text, re.IGNORECASE))
    closing = len(re.findall(rf"</{tag_name}>", text, re.IGNORECASE))
    return opening != closing


def parse_thinking_response(text: str) -> ThinkingParseResult:
    """Parse <thinking> and <final> sections from a model response."""
    raw = (text or "").strip()
    if not raw:
        return ThinkingParseResult(thinking=None, final_answer="", raw="")
    if _has_unbalanced_tag(raw, "thinking") or _has_unbalanced_tag(raw, "final"):
        return ThinkingParseResult(thinking=None, final_answer=raw, raw=raw)

    thinking_parts = [
        cleaned for match in _THINKING_PATTERN.finditer(raw) if (cleaned := _clean_section(match.group(1)))
    ]
    final_parts = [
        cleaned for match in _FINAL_PATTERN.finditer(raw) if (cleaned := _clean_section(match.group(1)))
    ]

    thinking = _truncate_thinking("\n\n".join(thinking_parts) if thinking_parts else None)

    if final_parts:
        final_answer = "\n\n".join(final_parts)
    elif thinking_parts:
        without_thinking = _THINKING_PATTERN.sub("", raw).strip()
        final_answer = _FINAL_PATTERN.sub("", without_thinking).strip() or raw
    else:
        final_answer = raw

    return ThinkingParseResult(thinking=thinking, final_answer=final_answer, raw=raw)


def parse_reasoning_api_response(response_data: dict[str, Any]) -> ThinkingParseResult:
    """Normalize providers that expose reasoning and answer content separately."""
    reasoning = response_data.get("reasoning_content") or response_data.get("reasoning")
    content = str(response_data.get("content", "") or "").strip()
    return ThinkingParseResult(
        thinking=_truncate_thinking(str(reasoning).strip()) if reasoning else None,
        final_answer=content,
        raw=content,
    )
