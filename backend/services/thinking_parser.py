"""Helpers for extracting structured thinking/final sections from model output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

MAX_THINKING_LENGTH = 4000
THINKING_TRUNCATION_SUFFIX = "\n...(推理过程已截断)"

_THINKING_PATTERN = re.compile(r"<thinking>(.*?)</thinking>", re.IGNORECASE | re.DOTALL)
_FINAL_PATTERN = re.compile(r"<final>(.*?)</final>", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class ThinkingParseResult:
    thinking: str | None
    final_answer: str
    raw: str


@dataclass(slots=True)
class StreamingThinkingChunk:
    channel: Literal["thinking", "final"]
    text: str


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


def _merge_stream_chunks(chunks: list[StreamingThinkingChunk]) -> list[StreamingThinkingChunk]:
    merged: list[StreamingThinkingChunk] = []
    for chunk in chunks:
        if not chunk.text:
            continue
        if merged and merged[-1].channel == chunk.channel:
            merged[-1].text += chunk.text
        else:
            merged.append(chunk)
    return merged


class StreamingThinkingParser:
    """Incrementally split streamed XML-tagged output into thinking/final chunks."""

    _TAGS = ("<thinking>", "</thinking>", "<final>", "</final>")

    def __init__(self) -> None:
        self._buffer = ""
        self._mode: Literal["thinking", "final"] | None = None
        self._saw_any_tag = False
        self._saw_final_tag = False

    def feed(self, chunk: str) -> list[StreamingThinkingChunk]:
        if not chunk:
            return []
        self._buffer += chunk
        return self._drain(final=False)

    def flush(self) -> list[StreamingThinkingChunk]:
        chunks = self._drain(final=True)
        if not self._buffer:
            return chunks

        remainder = self._buffer
        self._buffer = ""

        if self._mode == "thinking":
            chunks.append(StreamingThinkingChunk(channel="thinking", text=remainder))
        elif self._mode == "final":
            chunks.append(StreamingThinkingChunk(channel="final", text=remainder))
        elif not self._saw_any_tag:
            chunks.append(StreamingThinkingChunk(channel="final", text=remainder))
        elif not self._saw_final_tag and remainder.strip():
            chunks.append(StreamingThinkingChunk(channel="final", text=remainder))

        return _merge_stream_chunks(chunks)

    def _drain(self, *, final: bool) -> list[StreamingThinkingChunk]:
        chunks: list[StreamingThinkingChunk] = []

        while True:
            next_tag = self._find_next_tag()

            if self._mode == "thinking":
                if next_tag is not None and next_tag[1] in ("</thinking>", "<final>"):
                    index, tag = next_tag
                    prefix = self._buffer[:index]
                    if prefix:
                        chunks.append(StreamingThinkingChunk(channel="thinking", text=prefix))
                    self._buffer = self._buffer[index + len(tag) :]
                    if tag == "<final>":
                        self._mode = "final"
                        self._saw_any_tag = True
                        self._saw_final_tag = True
                    else:
                        self._mode = None
                    continue
                if final:
                    break
                break

            if self._mode == "final":
                if next_tag is not None and next_tag[1] == "</final>":
                    index, tag = next_tag
                    prefix = self._buffer[:index]
                    if prefix:
                        chunks.append(StreamingThinkingChunk(channel="final", text=prefix))
                    self._buffer = self._buffer[index + len(tag) :]
                    self._mode = None
                    continue
                if final:
                    break
                break

            if next_tag is not None:
                index, tag = next_tag
                prefix = self._buffer[:index]
                if prefix:
                    if not self._saw_any_tag:
                        if tag == "<thinking>" and not prefix.isspace():
                            chunks.append(StreamingThinkingChunk(channel="thinking", text=prefix))
                        elif tag == "<final>" and not prefix.isspace():
                            chunks.append(StreamingThinkingChunk(channel="final", text=prefix))
                    elif not self._saw_final_tag and not prefix.isspace():
                        chunks.append(StreamingThinkingChunk(channel="final", text=prefix))
                self._buffer = self._buffer[index + len(tag) :]
                if tag == "<thinking>":
                    self._mode = "thinking"
                    self._saw_any_tag = True
                elif tag == "<final>":
                    self._mode = "final"
                    self._saw_any_tag = True
                    self._saw_final_tag = True
                else:
                    self._saw_any_tag = True
                continue

            break

        return _merge_stream_chunks(chunks)

    def _find_next_tag(self) -> tuple[int, str] | None:
        matches = [(index, tag) for tag in self._TAGS if (index := self._buffer.find(tag)) != -1]
        if not matches:
            return None
        return min(matches, key=lambda item: item[0])


def parse_thinking_response(text: str) -> ThinkingParseResult:
    """Parse <thinking> and <final> sections from a model response."""
    raw = (text or "").strip()
    if not raw:
        return ThinkingParseResult(thinking=None, final_answer="", raw="")
    if _has_unbalanced_tag(raw, "thinking"):
        return ThinkingParseResult(thinking=None, final_answer=raw, raw=raw)

    thinking_parts = [
        cleaned
        for match in _THINKING_PATTERN.finditer(raw)
        if (cleaned := _clean_section(match.group(1)))
    ]
    final_parts = [
        cleaned
        for match in _FINAL_PATTERN.finditer(raw)
        if (cleaned := _clean_section(match.group(1)))
    ]

    thinking = _truncate_thinking("\n\n".join(thinking_parts) if thinking_parts else None)

    if final_parts:
        final_answer = "\n\n".join(final_parts)
    elif "<final>" in raw.lower():
        final_start = re.search(r"<final>", raw, re.IGNORECASE)
        assert final_start is not None
        final_answer = raw[final_start.end() :].strip() or raw
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
