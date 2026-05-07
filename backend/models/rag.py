"""Knowledge base and RAG domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RAGSource(BaseModel):
    id: str
    file_path: str
    relative_path: str
    extension: str
    file_hash: str | None = None
    modified_at: datetime | None = None
    size_bytes: int = 0
    status: str
    error: str | None = None
    provider: str
    doc_id: str
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RAGChunkHit(BaseModel):
    source_id: str
    source_path: str
    relative_path: str
    chunk_id: str
    position: int
    page_idx: int | None = None
    score: float
    text: str


class RAGIndexSummary(BaseModel):
    scanned: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    sources: list[RAGSource] = Field(default_factory=list)


class RAGQueryResult(BaseModel):
    answer: str
    citations: list[RAGChunkHit] = Field(default_factory=list)
    provider: str = "raganything"
    raw_result: Any | None = None
