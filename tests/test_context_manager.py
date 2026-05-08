"""Test context management functionality."""

import pytest

from backend.services.context_manager import ContextCompactor, TokenCounter


def test_token_counter():
    """Test basic token counting."""
    counter = TokenCounter()

    # Simple text
    text = "Hello, world!"
    tokens = counter.count_tokens(text)
    assert tokens > 0
    assert tokens < 10  # Should be around 3-4 tokens

    # Message with role
    message = {"role": "user", "content": "Hello, world!"}
    msg_tokens = counter.count_message_tokens(message)
    assert msg_tokens > tokens  # Should include overhead

    # Multiple messages
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    total_tokens = counter.count_messages_tokens(messages)
    assert total_tokens > 0


@pytest.mark.asyncio
async def test_context_compactor_no_compression_needed(db_session):
    """Test that compactor doesn't compress when under budget."""
    compactor = ContextCompactor(db_session)

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]

    # Large budget - no compression needed
    result = await compactor.compact_history(messages, max_tokens=10000)

    assert len(result) == len(messages)
    assert result == messages


@pytest.mark.asyncio
async def test_context_compactor_keeps_recent(db_session):
    """Test that compactor always keeps recent messages."""
    compactor = ContextCompactor(db_session)

    messages = [
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Message 2"},
        {"role": "assistant", "content": "Response 2"},
        {"role": "user", "content": "Message 3"},
        {"role": "assistant", "content": "Response 3"},
    ]

    # Very small budget - should keep at least min_recent_messages
    result = await compactor.compact_history(messages, max_tokens=100, min_recent_messages=2)

    # Should have at least 2 recent messages
    assert len(result) >= 2

    # Last messages should be preserved
    assert result[-1]["content"] == "Response 3"
    assert result[-2]["content"] == "Message 3"


def test_importance_estimation():
    """Test message importance scoring."""
    compactor = ContextCompactor(None)

    # User message with important keyword
    msg1 = {"role": "user", "content": "This is an important error message"}
    score1 = compactor.estimate_message_importance(msg1)
    assert score1 > 0.5

    # Regular assistant message
    msg2 = {"role": "assistant", "content": "Here's a simple response"}
    score2 = compactor.estimate_message_importance(msg2)
    assert 0.0 <= score2 <= 1.0

    # Message with multiple important keywords
    msg3 = {"role": "user", "content": "Critical bug: remember to fix this important issue"}
    score3 = compactor.estimate_message_importance(msg3)
    assert score3 > score1  # Should have higher score
