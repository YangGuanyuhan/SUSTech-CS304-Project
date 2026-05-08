from __future__ import annotations

import io

import pytest
from starlette.datastructures import UploadFile

from backend.config import get_settings
from backend.services.chat_file_service import ChatFileService
from backend.services.rag_service import RAGService, RAGServiceError


def _upload(filename: str, content: bytes = b"fake"):
    return UploadFile(file=io.BytesIO(content), filename=filename)


async def test_chat_file_upload_indexes_session_source(
    db_session, tmp_path, monkeypatch
):
    get_settings.cache_clear()
    monkeypatch.setenv("RAG_STORAGE_DIR", str(tmp_path / "rag"))
    monkeypatch.setattr(
        RAGService,
        "_extract_content_list",
        lambda self, file_path: [{"type": "text", "text": "Slides explain preemption.", "page_idx": 0}],
    )
    service = ChatFileService(db_session)

    summary = await service.upload_and_index(
        session_id="chat-1",
        files=[_upload("lecture.pptx")],
    )

    assert summary.indexed == 1
    assert summary.sources[0].relative_path == "lecture.pptx"
    assert service.list_files("chat-1")[0].relative_path == "lecture.pptx"
    assert not service.list_files("chat-2")
    get_settings.cache_clear()


async def test_chat_file_upload_rejects_unsupported_extension(db_session, tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("RAG_STORAGE_DIR", str(tmp_path / "rag"))
    service = ChatFileService(db_session)

    with pytest.raises(RAGServiceError):
        await service.upload_and_index(session_id="chat-1", files=[_upload("slides.ppt")])
    get_settings.cache_clear()


async def test_chat_file_delete_removes_source_from_session(db_session, tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("RAG_STORAGE_DIR", str(tmp_path / "rag"))
    monkeypatch.setattr(
        RAGService,
        "_extract_content_list",
        lambda self, file_path: [{"type": "text", "text": "The quiz is about threads.", "page_idx": 0}],
    )
    service = ChatFileService(db_session)
    summary = await service.upload_and_index(
        session_id="chat-1",
        files=[_upload("threads.pdf")],
    )

    deleted = service.delete_file(session_id="chat-1", source_id=summary.sources[0].id)

    assert deleted is True
    assert service.list_files("chat-1") == []
    assert not RAGService(db_session).search(
        "threads",
        owner_ids=[service.chat_owner_id("chat-1")],
    )
    get_settings.cache_clear()
