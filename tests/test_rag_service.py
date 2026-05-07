from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.db.models import RAGSourceRecord
from backend.services.rag_service import RAGService, RAGServiceError


class FakeRAGProvider:
    name = "raganything"

    def __init__(self):
        self.pdfs = []
        self.content_lists = []
        self.answers = []

    async def index_pdf(self, file_path, *, output_dir, doc_id):
        self.pdfs.append((file_path, output_dir, doc_id))

    async def insert_content_list(self, content_list, *, file_path, doc_id):
        self.content_lists.append((content_list, file_path, doc_id))

    async def answer(self, query, *, mode="hybrid"):
        self.answers.append((query, mode))
        return f"Answer for {query}"


class EmptyAnswerRAGProvider(FakeRAGProvider):
    async def answer(self, query, *, mode="hybrid"):
        self.answers.append((query, mode))
        return None


async def test_rag_indexes_markdown_and_searches_chunks(db_session, tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text(
        "# Course Policy\n\nThe final exam covers async Python and database indexing.",
        encoding="utf-8",
    )
    provider = FakeRAGProvider()
    service = RAGService(db_session, provider=provider)

    summary = await service.index_folder(".", workspace_root=str(tmp_path))

    assert summary.scanned == 1
    assert summary.indexed == 1
    assert summary.sources[0].status == "indexed"
    assert provider.content_lists[0][0][0]["type"] == "text"

    hits = service.search("database indexing")
    assert hits
    assert hits[0].relative_path == "notes.md"
    assert "database indexing" in hits[0].text


async def test_rag_skips_unchanged_files_by_hash(db_session, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("Campus shuttle schedule is updated weekly.", encoding="utf-8")
    provider = FakeRAGProvider()
    service = RAGService(db_session, provider=provider)

    first = await service.index_folder(".", workspace_root=str(tmp_path))
    second = await service.index_folder(".", workspace_root=str(tmp_path))

    assert first.indexed == 1
    assert second.skipped == 1
    assert len(provider.content_lists) == 1


async def test_rag_rejects_path_escape(db_session, tmp_path):
    service = RAGService(db_session, provider=FakeRAGProvider())
    outside = tmp_path.parent

    with pytest.raises(RAGServiceError):
        await service.index_folder(str(outside), workspace_root=str(tmp_path))


async def test_rag_marks_legacy_office_as_failed(db_session, tmp_path):
    legacy = tmp_path / "slides.ppt"
    legacy.write_bytes(b"legacy")
    service = RAGService(db_session, provider=FakeRAGProvider())

    summary = await service.index_folder(".", workspace_root=str(tmp_path))

    assert summary.failed == 1
    assert summary.sources[0].status == "failed"
    assert "Legacy Office formats" in (summary.sources[0].error or "")


async def test_rag_pdf_uses_provider_even_when_local_text_fallback_is_limited(db_session, tmp_path):
    pdf = tmp_path / "lecture.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real text pdf")
    provider = FakeRAGProvider()
    service = RAGService(db_session, provider=provider)

    summary = await service.index_folder(".", workspace_root=str(tmp_path))

    assert summary.indexed == 1
    assert provider.pdfs
    assert summary.sources[0].status == "indexed"


async def test_rag_query_returns_answer_with_citations(db_session, tmp_path):
    notes = tmp_path / "school.md"
    notes.write_text("The add/drop deadline is listed by the registrar.", encoding="utf-8")
    provider = FakeRAGProvider()
    service = RAGService(db_session, provider=provider)
    await service.index_folder(".", workspace_root=str(tmp_path))

    result = await service.query("add/drop deadline")

    assert "Answer for add/drop deadline" in result.answer
    assert result.citations
    assert "Sources:" in result.answer


async def test_rag_query_falls_back_to_llm_when_provider_returns_empty(
    db_session, tmp_path, monkeypatch
):
    notes = tmp_path / "school.md"
    notes.write_text("The add/drop deadline is Friday.", encoding="utf-8")

    async def fake_generate_chat(self, messages):
        assert "The add/drop deadline is Friday." in messages[-1]["content"]
        return "The add/drop deadline is Friday."

    from backend.services import rag_service

    monkeypatch.setattr(rag_service.LLMService, "generate_chat", fake_generate_chat)
    service = RAGService(db_session, provider=EmptyAnswerRAGProvider())
    await service.index_folder(".", workspace_root=str(tmp_path))

    result = await service.query("When is the add/drop deadline?")

    assert "Friday" in result.answer
    assert "Sources:" in result.answer


async def test_rag_list_sources_marks_stale_processing_as_failed(db_session, tmp_path):
    stale = RAGSourceRecord(
        file_path=str(tmp_path / "stuck.pdf"),
        relative_path="stuck.pdf",
        extension=".pdf",
        status="processing",
        provider="raganything",
        doc_id="stuck-doc",
        updated_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    db_session.add(stale)
    db_session.commit()

    sources = RAGService(db_session, provider=FakeRAGProvider()).list_sources()

    assert sources[0].status == "failed"
    assert "did not finish" in (sources[0].error or "")
