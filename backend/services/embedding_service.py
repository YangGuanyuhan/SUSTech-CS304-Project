"""Embedding generation service using configured LLM API.

Design principle: never silently return a fake embedding. Many OpenAI-compatible
endpoints (DashScope chat models, Claude, etc.) don't support /embeddings at all.
If real embeddings aren't available we return None and let the caller fall back
to pure keyword search, instead of poisoning the DB with hash-based vectors that
look like embeddings but carry no semantic information.
"""

from __future__ import annotations

import asyncio
import logging
import time

from openai import AsyncOpenAI, DefaultAsyncHttpxClient

from backend.services.runtime_settings import runtime_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings using the configured LLM API, or admit it can't.

    Probes the endpoint once and caches the verdict per (base_url, model) tuple
    so we don't pay the probe cost on every call.
    """

    # Class-level cache: key=(base_url, embedding_model) -> bool support
    _support_cache: dict[tuple[str, str], bool] = {}
    _probe_lock = asyncio.Lock()

    def __init__(self) -> None:
        pass

    def _resolve_embedding_model(self, chat_model: str) -> str:
        """Pick a likely embedding model name based on the configured chat model.

        These are heuristics — if they're wrong, the probe will catch it and
        we'll mark the endpoint unsupported.
        """
        m = chat_model.lower()
        if "gpt" in m or m.startswith("o1") or m.startswith("o3"):
            return "text-embedding-3-small"
        if "qwen" in m or "dashscope" in m:
            return "text-embedding-v3"
        if "glm" in m or "zhipu" in m:
            return "embedding-3"
        if "deepseek" in m:
            # DeepSeek as of late 2024 has no public embedding endpoint.
            # The probe will return False and we'll skip embeddings entirely.
            return "deepseek-embedding"
        # Default guess for OpenAI-compatible endpoints.
        return "text-embedding-3-small"

    def _build_client(self) -> tuple[AsyncOpenAI, str, str]:
        """Return (client, embedding_model, base_url_key)."""
        config = runtime_settings.get_llm_config()
        api_key = runtime_settings.get_secret_api_key()
        if not api_key:
            raise ValueError("No API key configured")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.base_url or None,
            http_client=DefaultAsyncHttpxClient(trust_env=False),
        )
        return client, self._resolve_embedding_model(config.model), config.base_url or ""

    async def _probe_support(self) -> bool:
        """Lazily check whether the configured endpoint actually supports embeddings.

        Cached per (base_url, embedding_model). One real call, with a short timeout.
        """
        try:
            client, model, base_url = self._build_client()
        except ValueError:
            return False

        cache_key = (base_url, model)
        if cache_key in self._support_cache:
            return self._support_cache[cache_key]

        async with self._probe_lock:
            if cache_key in self._support_cache:
                return self._support_cache[cache_key]

            started = time.perf_counter()
            try:
                # Tiny payload, short timeout — we just want a yes/no.
                await asyncio.wait_for(
                    client.embeddings.create(input="ok", model=model),
                    timeout=8.0,
                )
                supported = True
                logger.info(
                    "Embeddings supported on %s (model=%s, %.0fms)",
                    base_url or "<default>",
                    model,
                    (time.perf_counter() - started) * 1000,
                )
            except Exception as exc:
                supported = False
                logger.warning(
                    "Embeddings unavailable on %s (model=%s): %s. "
                    "Long-term memory will use keyword search only.",
                    base_url or "<default>",
                    model,
                    type(exc).__name__,
                )

            self._support_cache[cache_key] = supported
            return supported

    @classmethod
    def reset_probe_cache(cls) -> None:
        """Forget the probe verdict. Call this when LLM settings change."""
        cls._support_cache.clear()

    async def generate_embedding(self, text: str) -> list[float] | None:
        """Return a real embedding vector, or None if the endpoint can't produce one.

        Callers MUST handle None — never assume an embedding is always available.
        """
        if not text or not text.strip():
            return None

        if not await self._probe_support():
            return None

        try:
            client, model, _ = self._build_client()
            response = await asyncio.wait_for(
                client.embeddings.create(input=text, model=model),
                timeout=15.0,
            )
            return list(response.data[0].embedding)
        except Exception as exc:
            logger.warning("Embedding call failed: %s", exc)
            return None

    async def generate_embeddings(self, texts: list[str]) -> list[list[float] | None]:
        """Batch version. Each slot is either a real vector or None."""
        if not texts:
            return []

        if not await self._probe_support():
            return [None] * len(texts)

        try:
            client, model, _ = self._build_client()
            response = await asyncio.wait_for(
                client.embeddings.create(input=texts, model=model),
                timeout=30.0,
            )
            return [list(item.embedding) for item in response.data]
        except Exception as exc:
            logger.warning("Batch embedding call failed: %s", exc)
            return [None] * len(texts)

    @staticmethod
    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimension")
        dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        m1 = sum(a * a for a in vec1) ** 0.5
        m2 = sum(b * b for b in vec2) ** 0.5
        if m1 == 0 or m2 == 0:
            return 0.0
        return dot / (m1 * m2)
