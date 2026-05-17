from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.config import get_settings
from backend.db.models import RAGSourceRecord
from backend.models.rag import RAGDirectorySettings
from backend.services.rag_service import RAGAnythingProvider, RAGService, RAGServiceError


def shared_root() -> Path:
    return Path(get_settings().shared_workspace_dir).resolve()


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


class SlowAnswerRAGProvider(FakeRAGProvider):
    async def answer(self, query, *, mode="hybrid"):
        import asyncio

        self.answers.append((query, mode))
        await asyncio.sleep(1)
        return f"Slow answer for {query}"


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
    assert provider.content_lists == []

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
    assert provider.content_lists == []


async def test_rag_rejects_path_escape(db_session, tmp_path):
    service = RAGService(db_session, provider=FakeRAGProvider())
    outside = tmp_path.parent

    with pytest.raises(RAGServiceError):
        await service.index_folder(str(outside), workspace_root=str(tmp_path))


async def test_rag_directory_settings_round_trip(db_session, tmp_path):
    root = shared_root()
    default = root / "course-a"
    default.mkdir(parents=True)
    service = RAGService(db_session, provider=FakeRAGProvider())

    saved = service.save_directory_settings(
        RAGDirectorySettings(
            allowed_roots=[str(root)],
            default_root=str(default),
            recursive_default=False,
        )
    )
    loaded = service.get_directory_settings()

    assert saved.allowed_roots == [str(root.resolve())]
    assert loaded.default_root == str(default.resolve())
    assert loaded.recursive_default is False


async def test_rag_directory_settings_reject_invalid_paths(db_session, tmp_path):
    root = shared_root()
    root.mkdir()
    file_path = root / "not-a-folder.md"
    file_path.write_text("hello", encoding="utf-8")
    service = RAGService(db_session, provider=FakeRAGProvider())

    with pytest.raises(RAGServiceError):
        service.save_directory_settings(RAGDirectorySettings(default_root=str(file_path)))

    with pytest.raises(RAGServiceError):
        service.save_directory_settings(
            RAGDirectorySettings(
                allowed_roots=[str(root)],
                default_root=str(tmp_path.parent),
            )
        )


async def test_rag_resolve_index_scope_uses_default_root(db_session, tmp_path):
    root = shared_root()
    default = root / "course-a"
    default.mkdir(parents=True)
    service = RAGService(db_session, provider=FakeRAGProvider())
    service.save_directory_settings(
        RAGDirectorySettings(allowed_roots=[str(root)], default_root=str(default))
    )

    workspace_root, path = service.resolve_index_scope(path=None)

    assert workspace_root == str(root.resolve())
    assert path == "course-a"


async def test_rag_resolve_index_scope_rejects_unauthorized_absolute_path(db_session, tmp_path):
    root = shared_root()
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    service = RAGService(db_session, provider=FakeRAGProvider())
    service.save_directory_settings(
        RAGDirectorySettings(allowed_roots=[str(root)], default_root=str(root))
    )

    with pytest.raises(RAGServiceError):
        service.resolve_index_scope(path=str(outside))


async def test_rag_search_prefers_owner_ids_in_order(db_session, tmp_path):
    local_root = tmp_path / "local"
    chat_root = tmp_path / "chat"
    local_root.mkdir()
    chat_root.mkdir()
    (local_root / "global.md").write_text("The deadline is Monday.", encoding="utf-8")
    (chat_root / "uploaded.md").write_text("The deadline is Friday.", encoding="utf-8")
    service = RAGService(db_session, provider=FakeRAGProvider())

    await service.index_folder(".", workspace_root=str(local_root), owner_id="local-user")
    await service.index_folder(".", workspace_root=str(chat_root), owner_id="chat:abc")

    hits = service.search("deadline", owner_ids=["chat:abc", "local-user"], top_k=2)

    assert [hit.relative_path for hit in hits] == ["uploaded.md", "global.md"]


async def test_rag_query_falls_back_to_chat_chunks_for_generic_upload_question(
    db_session, tmp_path, monkeypatch
):
    chat_root = tmp_path / "chat"
    chat_root.mkdir()
    (chat_root / "upload.md").write_text(
        "This uploaded PDF is about CPU scheduling and preemption.",
        encoding="utf-8",
    )

    async def fake_generate_chat(self, messages):
        assert "CPU scheduling and preemption" in messages[-1]["content"]
        return "The uploaded PDF discusses CPU scheduling and preemption."

    from backend.services import rag_service

    monkeypatch.setattr(rag_service.LLMService, "generate_chat", fake_generate_chat)
    service = RAGService(db_session, provider=FakeRAGProvider())
    await service.index_folder(".", workspace_root=str(chat_root), owner_id="chat:abc")

    result = await service.query("Analyze my uploaded PDF", owner_ids=["chat:abc", "local-user"])

    assert result.citations
    assert result.citations[0].relative_path == "upload.md"
    assert "CPU scheduling" in result.answer


async def test_rag_marks_legacy_office_as_failed(db_session, tmp_path):
    legacy = tmp_path / "slides.ppt"
    legacy.write_bytes(b"legacy")
    service = RAGService(db_session, provider=FakeRAGProvider())

    summary = await service.index_folder(".", workspace_root=str(tmp_path))

    assert summary.failed == 1
    assert summary.sources[0].status == "failed"
    assert "Legacy Office formats" in (summary.sources[0].error or "")


async def test_rag_pdf_defaults_to_fast_content_insert(db_session, tmp_path, monkeypatch):
    pdf = tmp_path / "lecture.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real text pdf")
    provider = FakeRAGProvider()
    service = RAGService(db_session, provider=provider)
    monkeypatch.setattr(
        service,
        "_extract_content_list",
        lambda file_path: [{"type": "text", "text": "Fast PDF text", "page_idx": 0}],
    )

    summary = await service.index_folder(".", workspace_root=str(tmp_path))

    assert summary.indexed == 1
    assert provider.content_lists == []
    assert not provider.pdfs
    assert summary.sources[0].status == "indexed"


async def test_rag_pdf_can_use_mineru_when_configured(db_session, tmp_path, monkeypatch):
    pdf = tmp_path / "lecture.pdf"
    pdf.write_bytes(b"%PDF-1.4\nnot a real text pdf")
    provider = FakeRAGProvider()
    service = RAGService(db_session, provider=provider)
    monkeypatch.setattr(service.settings, "rag_pdf_parser", "mineru")
    monkeypatch.setattr(
        service,
        "_extract_content_list",
        lambda file_path: [{"type": "text", "text": "MinerU PDF text", "page_idx": 0}],
    )

    summary = await service.index_folder(".", workspace_root=str(tmp_path))

    assert summary.indexed == 1
    assert provider.pdfs
    assert not provider.content_lists


async def test_rag_query_returns_answer_with_citations(db_session, tmp_path, monkeypatch):
    notes = tmp_path / "school.md"
    notes.write_text("The add/drop deadline is listed by the registrar.", encoding="utf-8")
    provider = FakeRAGProvider()
    service = RAGService(db_session, provider=provider)
    monkeypatch.setattr(service.settings, "rag_enable_raganything_insert", True)
    monkeypatch.setattr(service.settings, "rag_enable_raganything_query", True)
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
    monkeypatch.setattr(service.settings, "rag_enable_raganything_query", True)
    await service.index_folder(".", workspace_root=str(tmp_path))

    result = await service.query("When is the add/drop deadline?")

    assert "Friday" in result.answer
    assert "Sources:" in result.answer


async def test_rag_query_defaults_to_local_citation_answer(db_session, tmp_path, monkeypatch):
    notes = tmp_path / "school.md"
    notes.write_text("The add/drop deadline is Friday.", encoding="utf-8")

    async def fake_generate_chat(self, messages):
        assert "The add/drop deadline is Friday." in messages[-1]["content"]
        return "The add/drop deadline is Friday."

    from backend.services import rag_service

    monkeypatch.setattr(rag_service.LLMService, "generate_chat", fake_generate_chat)
    provider = FakeRAGProvider()
    service = RAGService(db_session, provider=provider)
    await service.index_folder(".", workspace_root=str(tmp_path))

    result = await service.query("When is the add/drop deadline?")

    assert provider.answers == []
    assert "Friday" in result.answer
    assert result.raw_result == {"query_backend": "local-citations"}


async def test_rag_query_times_out_raganything_and_falls_back(db_session, tmp_path, monkeypatch):
    notes = tmp_path / "school.md"
    notes.write_text("The add/drop deadline is Friday.", encoding="utf-8")

    async def fake_generate_chat(self, messages):
        return "The add/drop deadline is Friday."

    from backend.services import rag_service

    monkeypatch.setattr(rag_service.LLMService, "generate_chat", fake_generate_chat)
    provider = SlowAnswerRAGProvider()
    service = RAGService(db_session, provider=provider)
    monkeypatch.setattr(service.settings, "rag_enable_raganything_query", True)
    monkeypatch.setattr(service.settings, "rag_query_timeout_seconds", 0.1)
    await service.index_folder(".", workspace_root=str(tmp_path))

    result = await service.query("When is the add/drop deadline?")

    assert "Friday" in result.answer
    assert result.raw_result["query_backend"] == "local-citations"
    assert "timed out" in result.raw_result["provider_error"]


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


def test_local_hash_embeddings_are_deterministic_and_dimensioned():
    first = RAGAnythingProvider._local_hash_embeddings(["add drop deadline"], dim=16)
    second = RAGAnythingProvider._local_hash_embeddings(["add drop deadline"], dim=16)

    assert first.shape == (1, 16)
    assert first.tolist() == second.tolist()


async def test_rag_pdf_index_adds_venv_scripts_to_path(monkeypatch, tmp_path):
    provider = RAGAnythingProvider()
    calls = []

    async def fake_call_supported(method_name, **kwargs):
        calls.append((method_name, kwargs))

    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(provider, "_call_supported", fake_call_supported)
    monkeypatch.setattr("backend.services.rag_service.shutil.which", lambda command: "mineru.EXE")

    pdf = tmp_path / "lecture.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    await provider.index_pdf(pdf, output_dir=tmp_path / "parsed", doc_id="doc-1")

    assert calls[0][0] == "process_document_complete"
    assert str(Path(sys.executable).parent) in os.environ["PATH"]
