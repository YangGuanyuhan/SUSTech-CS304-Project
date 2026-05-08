"""Test semantic search and embedding functionality."""

import pytest

from backend.models.memory import MemoryType
from backend.services.embedding_service import EmbeddingService
from backend.services.memory_service import MemoryService


def test_cosine_similarity():
    """Test cosine similarity calculation."""
    # Identical vectors
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    similarity = EmbeddingService.cosine_similarity(vec1, vec2)
    assert abs(similarity - 1.0) < 0.001

    # Orthogonal vectors
    vec3 = [1.0, 0.0, 0.0]
    vec4 = [0.0, 1.0, 0.0]
    similarity = EmbeddingService.cosine_similarity(vec3, vec4)
    assert abs(similarity) < 0.001

    # Opposite vectors
    vec5 = [1.0, 0.0, 0.0]
    vec6 = [-1.0, 0.0, 0.0]
    similarity = EmbeddingService.cosine_similarity(vec5, vec6)
    assert abs(similarity - (-1.0)) < 0.001


@pytest.mark.asyncio
async def test_fallback_embedding():
    """Test fallback embedding generation."""
    service = EmbeddingService()

    # Generate fallback embeddings
    text1 = "Hello world"
    text2 = "Hello world"
    text3 = "Different text"

    emb1 = service._fallback_embedding(text1)
    emb2 = service._fallback_embedding(text2)
    emb3 = service._fallback_embedding(text3)

    # Same text should produce same embedding
    assert emb1 == emb2

    # Different text should produce different embedding
    assert emb1 != emb3

    # Embeddings should be normalized (unit vectors)
    magnitude1 = sum(x * x for x in emb1) ** 0.5
    assert abs(magnitude1 - 1.0) < 0.001


@pytest.mark.asyncio
async def test_save_long_term_memory(db_session):
    """Test saving long-term memory with embedding."""
    service = MemoryService(db_session)

    # Save a memory
    memory = await service.save_long_term_memory(
        content="Python is a programming language",
        memory_type=MemoryType.FACTUAL,
        metadata={"topic": "programming"},
        importance_score=0.9,
        generate_embedding=True,
    )

    assert memory.id is not None
    assert memory.content == "Python is a programming language"
    assert memory.memory_type == MemoryType.FACTUAL
    assert memory.metadata == {"topic": "programming"}
    assert memory.importance_score == 0.9
    # Embedding should be generated (either real or fallback)
    assert memory.embedding is not None
    assert len(memory.embedding) > 0


@pytest.mark.asyncio
async def test_search_long_term_memories(db_session):
    """Test semantic search of long-term memories."""
    service = MemoryService(db_session)

    # Create some test memories
    await service.save_long_term_memory(
        content="Python is a high-level programming language",
        memory_type=MemoryType.FACTUAL,
        generate_embedding=True,
    )

    await service.save_long_term_memory(
        content="JavaScript is used for web development",
        memory_type=MemoryType.FACTUAL,
        generate_embedding=True,
    )

    await service.save_long_term_memory(
        content="User prefers dark mode in IDE",
        memory_type=MemoryType.USER_PREFERENCE,
        generate_embedding=True,
    )

    # Search for programming-related content
    results = await service.search_long_term_memories(
        query="programming languages", limit=5, semantic_threshold=0.0  # Low threshold for testing
    )

    # Should find at least the programming-related memories
    assert len(results) > 0

    # At least one result should contain programming-related content
    # (Note: with fallback embeddings, exact ordering may vary)
    programming_found = any(
        "programming" in mem.content.lower() or "language" in mem.content.lower()
        for mem in results
    )
    assert programming_found, "Should find at least one programming-related memory"


@pytest.mark.asyncio
async def test_search_by_memory_type(db_session):
    """Test filtering search by memory type."""
    service = MemoryService(db_session)

    # Create memories of different types
    await service.save_long_term_memory(
        content="User likes Python", memory_type=MemoryType.USER_PREFERENCE
    )

    await service.save_long_term_memory(
        content="Python was created in 1991", memory_type=MemoryType.FACTUAL
    )

    # Search only user preferences
    results = await service.search_long_term_memories(
        query="Python",
        memory_types=[MemoryType.USER_PREFERENCE],
        limit=10,
        semantic_threshold=0.0,
    )

    # Should only return user preference memories
    assert all(mem.memory_type == MemoryType.USER_PREFERENCE for mem in results)


@pytest.mark.asyncio
async def test_hybrid_search(db_session):
    """Test hybrid semantic + keyword search."""
    service = MemoryService(db_session)

    # Create a memory with specific keywords
    await service.save_long_term_memory(
        content="Remember to use async/await in Python for concurrent operations",
        memory_type=MemoryType.PROCEDURAL,
        generate_embedding=True,
    )

    # Search with exact keyword
    results = await service.search_long_term_memories(
        query="async await Python",
        limit=5,
        semantic_threshold=0.0,
        use_hybrid=True,
    )

    # Should find the memory
    assert len(results) > 0
    assert "async" in results[0].content.lower()


@pytest.mark.asyncio
async def test_list_long_term_memories(db_session):
    """Test listing long-term memories."""
    service = MemoryService(db_session)

    # Create some memories
    await service.save_long_term_memory(content="Memory 1", memory_type=MemoryType.FACTUAL)
    await service.save_long_term_memory(content="Memory 2", memory_type=MemoryType.EPISODIC)

    # List all memories
    all_memories = await service.list_long_term_memories()
    assert len(all_memories) >= 2

    # List by type
    factual_memories = await service.list_long_term_memories(memory_type=MemoryType.FACTUAL)
    assert all(mem.memory_type == MemoryType.FACTUAL for mem in factual_memories)


@pytest.mark.asyncio
async def test_delete_long_term_memory(db_session):
    """Test deleting long-term memory."""
    service = MemoryService(db_session)

    # Create a memory
    memory = await service.save_long_term_memory(
        content="Test memory to delete", memory_type=MemoryType.EPISODIC
    )

    memory_id = memory.id

    # Delete it
    deleted = await service.delete_long_term_memory(memory_id)
    assert deleted is True

    # Verify it's gone
    all_memories = await service.list_long_term_memories()
    assert not any(mem.id == memory_id for mem in all_memories)
