from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.db.database import get_db_session
from backend.main import app
from backend.services.rag_service import RAGService


@pytest.fixture()
def api_client(db_session) -> Iterator[TestClient]:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_rag_settings_api_round_trip(api_client, tmp_path):
    root = tmp_path / "notes"
    default = root / "course-a"
    default.mkdir(parents=True)

    response = api_client.put(
        "/api/rag/settings",
        json={
            "allowed_roots": [str(root)],
            "default_root": str(default),
            "recursive_default": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["allowed_roots"] == [str(root.resolve())]
    assert payload["default_root"] == str(default.resolve())
    assert payload["recursive_default"] is False

    loaded = api_client.get("/api/rag/settings")
    assert loaded.status_code == 200
    assert loaded.json()["data"] == payload


def test_rag_settings_api_rejects_default_outside_allowed_root(api_client, tmp_path):
    root = tmp_path / "notes"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    response = api_client.put(
        "/api/rag/settings",
        json={
            "allowed_roots": [str(root)],
            "default_root": str(outside),
            "recursive_default": True,
        },
    )

    assert response.status_code == 400
    assert "Default RAG directory" in response.json()["detail"]


def test_rag_index_folder_api_uses_default_directory(api_client, tmp_path):
    root = tmp_path / "notes"
    root.mkdir()
    (root / "policy.md").write_text("The add/drop deadline is Friday.", encoding="utf-8")
    api_client.put(
        "/api/rag/settings",
        json={
            "allowed_roots": [str(root)],
            "default_root": str(root),
            "recursive_default": True,
        },
    )

    response = api_client.post("/api/rag/index-folder", json={})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["indexed"] == 1
    assert payload["sources"][0]["relative_path"] == "policy.md"


def test_rag_index_folder_api_rejects_unauthorized_absolute_path(api_client, tmp_path):
    root = tmp_path / "notes"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    api_client.put(
        "/api/rag/settings",
        json={
            "allowed_roots": [str(root)],
            "default_root": str(root),
            "recursive_default": True,
        },
    )

    response = api_client.post("/api/rag/index-folder", json={"path": str(outside)})

    assert response.status_code == 400
    assert "outside the authorized directories" in response.json()["detail"]


def test_rag_session_file_upload_and_query(api_client, tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("RAG_STORAGE_DIR", str(tmp_path / "rag"))
    monkeypatch.setattr(
        RAGService,
        "_extract_content_list",
        lambda self, file_path: [
            {"type": "text", "text": "The uploaded deck covers preemption.", "page_idx": 0}
        ],
    )

    upload_response = api_client.post(
        "/api/rag/session-files/upload",
        data={"session_id": "chat-1"},
        files=[
            (
                "files",
                (
                    "assignment.pptx",
                    b"fake pptx bytes",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            )
        ],
    )
    assert upload_response.status_code == 200
    upload_payload = upload_response.json()["data"]
    assert upload_payload["indexed"] == 1
    assert upload_payload["sources"][0]["relative_path"] == "assignment.pptx"

    list_response = api_client.get("/api/rag/session-files", params={"session_id": "chat-1"})
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1

    query_response = api_client.post(
        "/api/rag/query",
        json={"query": "What does the uploaded deck cover?", "session_id": "chat-1"},
    )
    assert query_response.status_code == 200
    assert query_response.json()["data"]["citations"][0]["relative_path"] == "assignment.pptx"
    get_settings.cache_clear()


def test_rag_session_file_upload_rejects_old_ppt(api_client, tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("RAG_STORAGE_DIR", str(tmp_path / "rag"))

    response = api_client.post(
        "/api/rag/session-files/upload",
        data={"session_id": "chat-1"},
        files=[("files", ("slides.ppt", b"legacy", "application/vnd.ms-powerpoint"))],
    )

    assert response.status_code == 400
    assert "Only PDF, PPTX, DOCX, MD, and TXT" in response.json()["detail"]
    get_settings.cache_clear()
