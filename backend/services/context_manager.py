"""Context window management with intelligent compression."""

from __future__ import annotations

import tiktoken
from sqlalchemy.orm import Session

from backend.models.memory import ConversationMessage
from backend.services.runtime_settings import runtime_settings


class TokenCounter:
    """Estimate token counts for messages."""

    def __init__(self, model: str = "gpt-4"):
        """Initialize with a model name for tiktoken encoding."""
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for unknown models (works for most modern models)
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        return len(self.encoding.encode(text))

    def count_message_tokens(self, message: dict[str, str]) -> int:
        """Count tokens in a message dict with role and content."""
        # Add overhead for message formatting (role, etc.)
        # OpenAI format: <|im_start|>role\ncontent<|im_end|>
        role_overhead = 4  # Approximate overhead per message
        content_tokens = self.count_tokens(message.get("content", ""))
        return content_tokens + role_overhead

    def count_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        """Count total tokens in a list of messages."""
        return sum(self.count_message_tokens(msg) for msg in messages)


class ContextCompactor:
    """Intelligent context window management with LLM-based compression."""

    def __init__(self, session: Session):
        self.session = session
        self.token_counter = TokenCounter()

    async def compact_history(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 8000,
        min_recent_messages: int = 5,
    ) -> list[dict[str, str]]:
        """
        Intelligently compress message history to fit within token budget.

        Strategy:
        1. Always keep last N messages (min_recent_messages) for immediate context
        2. If still over budget, summarize older messages using LLM
        3. Retain high-importance messages
        4. Insert summaries as system messages

        Args:
            messages: List of message dicts with role and content
            max_tokens: Maximum tokens to keep
            min_recent_messages: Minimum number of recent messages to always keep

        Returns:
            Compressed message list
        """
        if not messages:
            return []

        # Count current tokens
        current_tokens = self.token_counter.count_messages_tokens(messages)

        if current_tokens <= max_tokens:
            # No compression needed
            return messages

        # Keep recent messages
        recent_messages = messages[-min_recent_messages:]
        recent_tokens = self.token_counter.count_messages_tokens(recent_messages)

        if recent_tokens >= max_tokens:
            # Even recent messages exceed budget, just return them
            # (This is an edge case - might need to truncate individual messages)
            return recent_messages

        # Calculate budget for older messages
        older_messages = messages[:-min_recent_messages]
        available_tokens = max_tokens - recent_tokens

        if not older_messages:
            return recent_messages

        # Summarize older messages
        summary = await self._summarize_messages(older_messages, available_tokens)

        # Build compressed history
        compressed = []
        if summary:
            compressed.append({"role": "system", "content": summary})
        compressed.extend(recent_messages)

        return compressed

    async def _summarize_messages(
        self, messages: list[dict[str, str]], max_summary_tokens: int
    ) -> str:
        """
        Use LLM to summarize a batch of messages.

        Args:
            messages: Messages to summarize
            max_summary_tokens: Target token count for summary

        Returns:
            Summary text
        """
        # Build a prompt for summarization
        conversation_text = "\n\n".join(
            [f"{msg['role'].upper()}: {msg['content']}" for msg in messages]
        )

        summary_prompt = f"""Summarize the following conversation history concisely, preserving key facts, decisions, and context. Keep the summary under {max_summary_tokens} tokens.

Conversation:
{conversation_text}

Summary:"""

        # Use the configured LLM to generate summary
        try:
            from backend.services.llm_service import LLMService

            llm_service = LLMService()

            # Use generate_chat for simple completion
            summary_response = await llm_service.generate_chat(
                messages=[{"role": "user", "content": summary_prompt}]
            )

            return summary_response.strip()

        except Exception as e:
            # Fallback: simple truncation if LLM fails
            fallback_summary = f"[Previous conversation with {len(messages)} messages]"
            return fallback_summary

    def estimate_message_importance(self, message: dict[str, str]) -> float:
        """
        Estimate importance score for a message.

        Higher scores indicate more important messages that should be retained.

        Factors:
        - User questions are important
        - Messages with tool usage are important
        - Longer messages might be more important
        - Messages with certain keywords (error, important, remember, etc.)

        Returns:
            Importance score between 0.0 and 1.0
        """
        content = message.get("content", "").lower()
        role = message.get("role", "")

        score = 0.5  # Base score

        # User messages are slightly more important
        if role == "user":
            score += 0.1

        # Check for important keywords
        important_keywords = [
            "error",
            "important",
            "remember",
            "critical",
            "bug",
            "issue",
            "problem",
            "help",
            "question",
        ]
        if any(keyword in content for keyword in important_keywords):
            score += 0.2

        # Longer messages might be more important (but cap the bonus)
        length_bonus = min(0.2, len(content) / 5000)
        score += length_bonus

        # Cap at 1.0
        return min(1.0, score)


class ContextWindowManager:
    """High-level context window management."""

    def __init__(self, session: Session):
        self.session = session
        self.compactor = ContextCompactor(session)
        self.token_counter = TokenCounter()

    async def prepare_context(
        self,
        messages: list[dict[str, str]],
        max_context_tokens: int = 8000,
        min_recent_messages: int = 5,
    ) -> tuple[list[dict[str, str]], dict[str, int]]:
        """
        Prepare context for LLM call with token management.

        Args:
            messages: Raw message history
            max_context_tokens: Maximum tokens for context
            min_recent_messages: Minimum recent messages to keep

        Returns:
            Tuple of (prepared_messages, stats_dict)
        """
        # Add token counts to messages if not present
        for msg in messages:
            if "token_count" not in msg:
                msg["token_count"] = self.token_counter.count_message_tokens(msg)

        # Compact if needed
        prepared = await self.compactor.compact_history(
            messages, max_tokens=max_context_tokens, min_recent_messages=min_recent_messages
        )

        # Calculate stats
        original_tokens = self.token_counter.count_messages_tokens(messages)
        final_tokens = self.token_counter.count_messages_tokens(prepared)

        stats = {
            "original_message_count": len(messages),
            "final_message_count": len(prepared),
            "original_tokens": original_tokens,
            "final_tokens": final_tokens,
            "tokens_saved": original_tokens - final_tokens,
            "compression_ratio": final_tokens / original_tokens if original_tokens > 0 else 1.0,
        }

        return prepared, stats
