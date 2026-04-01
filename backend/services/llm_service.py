"""OpenAI-compatible LLM service."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, DefaultAsyncHttpxClient
from openai.types.chat import ChatCompletionMessageParam

from backend.services.runtime_settings import runtime_settings


class LLMConfigurationError(ValueError):
    """Raised when runtime LLM settings are incomplete or unsupported."""


class LLMConnectionError(RuntimeError):
    """Raised when a connection test to the configured LLM fails."""


class LLMService:
    """OpenAI-compatible chat completion service backed by runtime settings."""

    def _build_client(self) -> tuple[AsyncOpenAI, str]:
        config = runtime_settings.get_llm_config()
        api_key = runtime_settings.get_secret_api_key()
        if config.provider.strip().lower() != "openai":
            raise LLMConfigurationError("Only OpenAI-compatible providers are supported right now.")
        if not api_key:
            raise LLMConfigurationError("No API key is configured. Open the LLM settings panel first.")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.base_url or None,
            http_client=DefaultAsyncHttpxClient(trust_env=False),
        )
        return client, config.model

    async def create_chat_completion(
        self,
        messages: list[dict[str, Any]] | list[ChatCompletionMessageParam],
        *,
        tools: list[dict[str, Any]] | None = None,
    ):
        """Return a non-streaming chat completion, optionally with tool definitions."""

        client, model = self._build_client()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            return await client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover - network and remote behavior vary
            raise LLMConnectionError(str(exc)) from exc

    async def stream_chat(self, messages: list[ChatCompletionMessageParam]) -> AsyncIterator[str]:
        """Stream a chat completion token-by-token."""

        client, model = self._build_client()
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    async def stream_chat_with_fallback(
        self,
        messages: list[ChatCompletionMessageParam],
        *,
        first_chunk_timeout: float = 6.0,
    ) -> AsyncIterator[str]:
        """Stream when available, otherwise fall back to a normal completion."""

        queue: asyncio.Queue[str | None] = asyncio.Queue()
        first_chunk_seen = False
        stream_error: Exception | None = None

        async def produce() -> None:
            nonlocal stream_error
            try:
                async for chunk in self.stream_chat(messages):
                    await queue.put(chunk)
            except Exception as exc:
                stream_error = exc
            finally:
                await queue.put(None)

        task = asyncio.create_task(produce())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=first_chunk_timeout if not first_chunk_seen else None)
                except asyncio.TimeoutError:
                    task.cancel()
                    fallback = await self.generate_chat(messages)
                    if fallback:
                        yield fallback
                    return

                if item is None:
                    if stream_error is not None:
                        raise stream_error
                    break

                first_chunk_seen = True
                yield item
        finally:
            if not task.done():
                task.cancel()

    async def generate_chat(self, messages: list[ChatCompletionMessageParam]) -> str:
        """Return a full chat completion."""

        response = await self.create_chat_completion(messages)
        return (response.choices[0].message.content or "").strip()

    async def test_connection(self) -> dict[str, object]:
        """Run a minimal completion against the configured endpoint."""

        started = time.perf_counter()
        try:
            client, model = self._build_client()
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with the single word: pong"}],
                max_tokens=8,
                temperature=0,
            )
        except Exception as exc:  # pragma: no cover - network and remote behavior vary
            raise LLMConnectionError(str(exc)) from exc

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        content = response.choices[0].message.content or ""
        return {"ok": True, "latency_ms": latency_ms, "model": model, "preview": content[:80]}
