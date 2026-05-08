"""Chat-scoped file upload service backed by the generic RAG indexer."""

from __future__ import annotations

import contextlib
import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.rag import RAGIndexSummary, RAGSource
from backend.services.rag_service import RAGService, RAGServiceError


CHAT_FILE_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", ".txt"}
MAX_CHAT_FILE_BYTES = 50 * 1024 * 1024
MAX_CHAT_FILES_PER_UPLOAD = 10
CHAT_FILE_CONTEXT_CHUNK_LIMIT = 60
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")
_SAFE_SESSION_RE = re.compile(r"[^A-Za-z0-9._-]+")


class ChatFileService:
    """Owns upload storage and chat-session scoping for file-based Q&A."""

    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()
        self.rag = RAGService(session)

    @staticmethod
    def chat_owner_id(session_id: str) -> str:
        cleaned = str(session_id or "").strip()
        if not cleaned:
            raise RAGServiceError("`session_id` is required for chat file uploads.")
        return f"chat:{cleaned}"

    def query_owner_ids(self, session_id: str) -> list[str]:
        return [self.chat_owner_id(session_id), "local-user"]

    def list_files(self, session_id: str) -> list[RAGSource]:
        return self.rag.list_sources(owner_id=self.chat_owner_id(session_id))

    async def upload_and_index(
        self,
        *,
        session_id: str,
        files: list[UploadFile],
    ) -> RAGIndexSummary:
        if not files:
            raise RAGServiceError("At least one file is required.")
        if len(files) > MAX_CHAT_FILES_PER_UPLOAD:
            raise RAGServiceError(f"Upload at most {MAX_CHAT_FILES_PER_UPLOAD} files at a time.")

        owner_id = self.chat_owner_id(session_id)
        upload_dir = self._upload_dir(session_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        summary = RAGIndexSummary(scanned=len(files))
        for upload in files:
            original_name = self._safe_filename(upload.filename or "uploaded-file")
            extension = Path(original_name).suffix.lower()
            if extension not in CHAT_FILE_EXTENSIONS:
                raise RAGServiceError(
                    "Only PDF, PPTX, DOCX, MD, and TXT uploads are supported. Convert old PPT/DOC files first."
                )
            stored_path = upload_dir / f"{uuid4().hex}-{original_name}"
            await self._save_upload(upload, stored_path)
            source = await self.rag.index_file(
                stored_path,
                workspace_root=str(upload_dir),
                owner_id=owner_id,
                relative_path=original_name,
            )
            summary.sources.append(source)
            if source.status == "indexed":
                summary.indexed += 1
            elif source.status == "failed":
                summary.failed += 1
        return summary

    def delete_file(self, *, session_id: str, source_id: str) -> bool:
        owner_id = self.chat_owner_id(session_id)
        source = next((item for item in self.list_files(session_id) if item.id == source_id), None)
        if source is None:
            return False
        deleted = self.rag.delete_source(source_id, owner_id=owner_id)
        if deleted:
            file_path = Path(source.file_path)
            if self._is_inside_upload_root(file_path):
                with contextlib.suppress(OSError):
                    file_path.unlink()
        return deleted

    def _upload_dir(self, session_id: str) -> Path:
        safe_session = _SAFE_SESSION_RE.sub("_", str(session_id).strip())[:120]
        if not safe_session:
            raise RAGServiceError("`session_id` is required for chat file uploads.")
        return (Path(self.settings.rag_storage_dir) / "uploads" / safe_session).resolve()

    def _is_inside_upload_root(self, file_path: Path) -> bool:
        upload_root = (Path(self.settings.rag_storage_dir) / "uploads").resolve()
        try:
            file_path.resolve().relative_to(upload_root)
        except ValueError:
            return False
        return True

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename).name.strip() or "uploaded-file"
        name = _SAFE_NAME_RE.sub("_", name)
        return name[:180] or "uploaded-file"

    async def _save_upload(self, upload: UploadFile, target: Path) -> None:
        bytes_written = 0
        try:
            with target.open("wb") as handle:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > MAX_CHAT_FILE_BYTES:
                        raise RAGServiceError("Each uploaded file must be 50 MB or smaller.")
                    handle.write(chunk)
        except Exception:
            with contextlib.suppress(OSError):
                target.unlink()
            raise
        finally:
            with contextlib.suppress(Exception):
                await upload.close()
