"""Local knowledge base service backed by RAG-Anything."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import inspect
import json
import os
import re
import shutil
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.models import RAGChunkRecord, RAGSourceRecord
from backend.db.repositories import UserPreferenceRepository
from backend.models.rag import (
    RAGChunkHit,
    RAGDirectorySettings,
    RAGIndexSummary,
    RAGQueryResult,
    RAGSource,
)
from backend.services.llm_service import LLMService
from backend.services.runtime_settings import runtime_settings
from backend.services.shared_workspace_service import SharedWorkspaceError, SharedWorkspaceService

try:
    from markitdown import MarkItDown
except ImportError:  # pragma: no cover - optional at test time
    MarkItDown = None


SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx", ".pptx", ".doc", ".ppt"}
OLD_OFFICE_EXTENSIONS = {".doc", ".ppt"}
_WORD_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
RAG_DIRECTORY_SETTINGS_KEY = "rag_directory_settings"


class RAGServiceError(ValueError):
    """Raised when RAG input is invalid or processing fails."""


class RAGProviderError(RuntimeError):
    """Raised when the configured RAG provider cannot complete a request."""


class RAGProvider(Protocol):
    name: str

    async def index_pdf(self, file_path: Path, *, output_dir: Path, doc_id: str) -> None:
        pass

    async def insert_content_list(
        self,
        content_list: list[dict[str, Any]],
        *,
        file_path: Path,
        doc_id: str,
    ) -> None:
        pass

    async def answer(self, query: str, *, mode: str = "hybrid") -> Any:
        pass


class RAGAnythingProvider:
    """Thin RAG-Anything adapter with text-first configuration."""

    name = "raganything"

    def __init__(self) -> None:
        self._rag: Any | None = None

    @staticmethod
    def _ensure_executable_dir_on_path() -> str:
        scripts_dir = str(Path(sys.executable).parent)
        path_parts = os.environ.get("PATH", "").split(os.pathsep)
        if scripts_dir not in path_parts:
            os.environ["PATH"] = f"{scripts_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        return scripts_dir

    def _build_rag(self) -> Any:
        try:
            from lightrag.llm.openai import openai_complete_if_cache
            from lightrag.utils import EmbeddingFunc
            from raganything import RAGAnything, RAGAnythingConfig
        except ImportError as exc:  # pragma: no cover - depends on optional dependency
            raise RAGProviderError(
                "RAG-Anything is not installed. Run `uv sync` after installing the "
                "`raganything` dependency."
            ) from exc

        settings = get_settings()
        llm_config = runtime_settings.get_llm_config()
        api_key = runtime_settings.get_secret_api_key()
        if not api_key:
            raise RAGProviderError("No LLM API key is configured for RAG-Anything.")

        working_dir = Path(settings.rag_storage_dir) / "raganything"
        working_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_executable_dir_on_path()

        config = RAGAnythingConfig(
            working_dir=str(working_dir),
            parser="mineru",
            parse_method="txt",
            enable_image_processing=False,
            enable_table_processing=False,
            enable_equation_processing=False,
        )

        def llm_model_func(
            prompt: str,
            system_prompt: str | None = None,
            history_messages: list[dict[str, Any]] | None = None,
            **kwargs: Any,
        ):
            return openai_complete_if_cache(
                llm_config.model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                api_key=api_key,
                base_url=llm_config.base_url,
                **kwargs,
            )

        if settings.rag_embedding_provider.lower() == "openai":
            from lightrag.llm.openai import openai_embed

            async def embed_texts(texts: list[str]):
                embed_callable = getattr(openai_embed, "func", openai_embed)
                return await embed_callable(
                    texts,
                    model=settings.rag_embedding_model,
                    api_key=api_key,
                    base_url=llm_config.base_url,
                )

        else:

            async def embed_texts(texts: list[str]):
                return self._local_hash_embeddings(texts, dim=settings.rag_embedding_dim)

        embedding_func = EmbeddingFunc(
            embedding_dim=settings.rag_embedding_dim,
            max_token_size=8192,
            func=embed_texts,
        )

        rag = RAGAnything(
            config=config,
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
        )
        # Direct content-list insertion for md/txt/docx/pptx does not need a document
        # parser. RAG-Anything checks parser installation before initializing
        # LightRAG, so skip that parser gate for text-first indexing.
        rag._parser_installation_checked = True
        return rag

    @staticmethod
    def _local_hash_embeddings(texts: list[str], *, dim: int):
        import numpy as np

        vectors = np.zeros((len(texts), dim), dtype=np.float32)
        for row, text in enumerate(texts):
            normalized = re.sub(r"\s+", " ", text.lower()).strip()
            terms = _WORD_RE.findall(normalized)
            compact = re.sub(r"\s+", "", normalized)
            terms.extend(compact[index : index + 2] for index in range(max(len(compact) - 1, 0)))
            if not terms and normalized:
                terms = [normalized]
            for term in terms:
                digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
                column = int.from_bytes(digest[:4], "little") % dim
                sign = 1.0 if digest[4] & 1 else -1.0
                vectors[row, column] += sign
            norm = np.linalg.norm(vectors[row])
            if norm > 0:
                vectors[row] /= norm
        return vectors

    def _rag_instance(self) -> Any:
        if self._rag is None:
            self._rag = self._build_rag()
        return self._rag

    async def _call_supported(self, method_name: str, **kwargs: Any) -> Any:
        method = getattr(self._rag_instance(), method_name)
        try:
            signature = inspect.signature(method)
            supported_kwargs = {
                key: value for key, value in kwargs.items() if key in signature.parameters
            }
        except (TypeError, ValueError):
            supported_kwargs = kwargs
        return await method(**supported_kwargs)

    async def _ensure_ready_for_content_insert(self) -> None:
        rag = self._rag_instance()
        result = await rag._ensure_lightrag_initialized()
        if isinstance(result, dict) and not result.get("success", False):
            raise RAGProviderError(str(result.get("error") or "LightRAG initialization failed."))
        if getattr(rag, "lightrag", None) is None:
            raise RAGProviderError("LightRAG initialization failed before content insertion.")

    async def index_pdf(self, file_path: Path, *, output_dir: Path, doc_id: str) -> None:
        self._ensure_executable_dir_on_path()
        if shutil.which("mineru") is None:
            raise RAGProviderError(
                "PDF indexing requires the MinerU command. Install it with "
                '`uv pip install -U "mineru[core]"`, or index converted md/txt/docx/pptx files.'
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        await self._call_supported(
            "process_document_complete",
            file_path=str(file_path),
            output_dir=str(output_dir),
            parse_method="txt",
            doc_id=doc_id,
        )

    async def insert_content_list(
        self,
        content_list: list[dict[str, Any]],
        *,
        file_path: Path,
        doc_id: str,
    ) -> None:
        await self._ensure_ready_for_content_insert()
        await self._call_supported(
            "insert_content_list",
            content_list=content_list,
            file_path=str(file_path),
            doc_id=doc_id,
            display_stats=False,
        )

    async def answer(self, query: str, *, mode: str = "hybrid") -> Any:
        await self._ensure_ready_for_content_insert()
        return await self._rag_instance().aquery(query, mode=mode)


class RAGService:
    """Coordinate local folder indexing, metadata storage, and RAG queries."""

    def __init__(self, session: Session, provider: RAGProvider | None = None):
        self.session = session
        self.settings = get_settings()
        self.provider = provider or RAGAnythingProvider()
        self.preferences = UserPreferenceRepository(session)

    def status(self) -> dict[str, Any]:
        llm_config = runtime_settings.get_llm_config()
        raganything_installed = True
        raganything_version: str | None = None
        install_error: str | None = None
        try:
            import importlib.metadata as metadata

            raganything_version = metadata.version("raganything")
        except Exception as exc:
            raganything_installed = False
            install_error = str(exc)

        raganything_required = (
            self.settings.rag_enable_raganything_insert
            or self.settings.rag_enable_raganything_query
        )
        ready = bool(llm_config.api_key_configured) and (
            raganything_installed or not raganything_required
        )
        scripts_dir = str(Path(sys.executable).parent)
        mineru_command = shutil.which(
            "mineru",
            path=f"{scripts_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        )
        fast_pdf_parser = self._fast_pdf_parser_name()
        pdf_parser = self.settings.rag_pdf_parser.lower()
        pdf_parser_ready = bool(mineru_command) if pdf_parser == "mineru" else bool(fast_pdf_parser)
        pdf_parser_command = mineru_command if pdf_parser == "mineru" else fast_pdf_parser
        issues: list[str] = []
        if not raganything_installed:
            message = "raganything is not installed. Run `uv sync`."
            if raganything_required:
                issues.append(message)
        if not llm_config.api_key_configured:
            issues.append("LLM API key is not configured. Set it in Settings or `.env`.")

        return {
            "provider": self.provider.name,
            "ready": ready,
            "issues": issues,
            "raganything_installed": raganything_installed,
            "raganything_version": raganything_version,
            "install_error": install_error,
            "llm_provider": llm_config.provider,
            "llm_model": llm_config.model,
            "llm_api_key_configured": llm_config.api_key_configured,
            "embedding_provider": self.settings.rag_embedding_provider,
            "embedding_model": (
                self.settings.rag_embedding_model
                if self.settings.rag_embedding_provider.lower() == "openai"
                else "local-hash"
            ),
            "embedding_dim": self.settings.rag_embedding_dim,
            "pdf_parser": self.settings.rag_pdf_parser,
            "mineru_fallback_enabled": self.settings.rag_enable_mineru_fallback,
            "raganything_insert_enabled": self.settings.rag_enable_raganything_insert,
            "raganything_query_enabled": self.settings.rag_enable_raganything_query,
            "index_backend": (
                "raganything+lightrag"
                if self.settings.rag_enable_raganything_insert
                else "local-chunks"
            ),
            "query_backend": (
                "raganything+lightrag"
                if self.settings.rag_enable_raganything_query
                else "local-citations"
            ),
            "pdf_parser_ready": pdf_parser_ready,
            "pdf_parser_command": pdf_parser_command,
            "fast_pdf_parser": fast_pdf_parser,
            "mineru_command": mineru_command,
            "storage_dir": self.settings.rag_storage_dir,
            "index_timeout_seconds": self.settings.rag_index_timeout_seconds,
            "query_timeout_seconds": self.settings.rag_query_timeout_seconds,
            "pdf_note": (
                "PDF indexing defaults to fast PyMuPDF4LLM extraction. MinerU is optional for "
                "scanned or image-heavy PDFs and may be slow on laptops."
            ),
        }

    def get_directory_settings(self) -> RAGDirectorySettings:
        record = next(
            (
                item
                for item in self.preferences.list(key_prefix=RAG_DIRECTORY_SETTINGS_KEY)
                if item.key == RAG_DIRECTORY_SETTINGS_KEY
            ),
            None,
        )
        if record is None:
            return self._normalize_directory_settings(RAGDirectorySettings())
        try:
            return self._normalize_directory_settings(
                RAGDirectorySettings.model_validate(json.loads(record.value))
            )
        except Exception:
            return self._normalize_directory_settings(RAGDirectorySettings())

    def save_directory_settings(
        self,
        settings: RAGDirectorySettings,
        *,
        owner_id: str = "local-user",
    ) -> RAGDirectorySettings:
        normalized = self._normalize_directory_settings(settings)
        self.preferences.upsert(
            key=RAG_DIRECTORY_SETTINGS_KEY,
            value=normalized.model_dump_json(),
            owner_id=owner_id,
        )
        return normalized

    def _normalize_directory_settings(
        self,
        settings: RAGDirectorySettings,
    ) -> RAGDirectorySettings:
        shared = SharedWorkspaceService()
        shared_root = shared.root()
        allowed_roots = [str(shared_root)]

        default_root: str | None = None
        if settings.default_root and settings.default_root.strip():
            try:
                default_root = str(shared.resolve_workspace_root(settings.default_root))
            except SharedWorkspaceError as exc:
                raise RAGServiceError(
                    "Default RAG directory must be inside the shared workspace."
                ) from exc
        else:
            default_root = str(shared_root)

        return RAGDirectorySettings(
            allowed_roots=allowed_roots,
            default_root=default_root,
            recursive_default=bool(settings.recursive_default),
        )

    def resolve_index_scope(
        self,
        *,
        path: str | None = None,
        workspace_root: str | None = None,
    ) -> tuple[str, str]:
        shared = SharedWorkspaceService()
        requested_text = (path or ".").strip() or "."
        try:
            if workspace_root and workspace_root.strip():
                base = shared.resolve_workspace_root(workspace_root)
            else:
                base = shared.resolve_workspace_root(self.get_directory_settings().default_root)
            candidate = shared.resolve_path(requested_text, base=base)
        except SharedWorkspaceError as exc:
            raise RAGServiceError("Requested RAG path is outside the shared workspace.") from exc

        if not candidate.is_dir():
            raise RAGServiceError(f"`{candidate}` is not a directory.")
        shared_root = shared.root()
        relative = candidate.relative_to(shared_root)
        return str(shared_root), "." if str(relative) == "." else relative.as_posix()

    def _resolve_existing_directory(self, value: str, *, field_name: str) -> Path:
        try:
            path = Path(value).expanduser().resolve(strict=True)
        except FileNotFoundError as exc:
            raise RAGServiceError(f"`{field_name}` directory `{value}` does not exist.") from exc
        if not path.is_dir():
            raise RAGServiceError(f"`{field_name}` must be a directory.")
        return path

    def _find_authorized_root(self, candidate: Path, allowed_roots: list[str]) -> Path | None:
        matches: list[Path] = []
        for raw_root in allowed_roots:
            root = Path(raw_root).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            matches.append(root)
        if not matches:
            return None
        return max(matches, key=lambda item: len(str(item)))

    def _fast_pdf_parser_name(self) -> str | None:
        if importlib.util.find_spec("pymupdf4llm") is not None:
            return "pymupdf4llm"
        if importlib.util.find_spec("pypdf") is not None:
            return "pypdf"
        return None

    def list_sources(self, *, owner_id: str = "local-user") -> list[RAGSource]:
        self._fail_stale_processing_sources(owner_id=owner_id)
        stmt = (
            select(RAGSourceRecord)
            .where(RAGSourceRecord.owner_id == owner_id)
            .order_by(RAGSourceRecord.updated_at.desc(), RAGSourceRecord.relative_path.asc())
        )
        return [self._source_model(record) for record in self.session.execute(stmt).scalars()]

    def _fail_stale_processing_sources(self, *, owner_id: str) -> None:
        timeout_seconds = max(int(self.settings.rag_index_timeout_seconds), 30)
        now = datetime.now(UTC)
        stmt = select(RAGSourceRecord).where(
            RAGSourceRecord.owner_id == owner_id,
            RAGSourceRecord.status == "processing",
        )
        changed = False
        for source in self.session.execute(stmt).scalars():
            updated_at = source.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            if (now - updated_at).total_seconds() <= timeout_seconds:
                continue
            source.status = "failed"
            source.error = (
                "Previous indexing run did not finish before the timeout. Retry with a smaller "
                "folder or raise RAG_INDEX_TIMEOUT_SECONDS."
            )
            source.updated_at = now
            changed = True
        if changed:
            self.session.commit()

    async def index_folder(
        self,
        folder_path: str,
        *,
        workspace_root: str,
        recursive: bool = True,
        extensions: list[str] | None = None,
        owner_id: str = "local-user",
    ) -> RAGIndexSummary:
        base = self._resolve_path(workspace_root, folder_path)
        if not base.is_dir():
            raise RAGServiceError(f"`{base}` is not a directory.")
        if isinstance(self.provider, RAGAnythingProvider) and (
            self.settings.rag_enable_raganything_insert
            or self.settings.rag_enable_raganything_query
        ):
            status = self.status()
            if not status["ready"]:
                raise RAGProviderError("; ".join(status["issues"]))

        allowed = self._normalize_extensions(extensions)
        files = self._iter_files(base, recursive=recursive, allowed_extensions=allowed)
        summary = RAGIndexSummary(scanned=len(files))
        for file_path in files:
            try:
                source, changed = await self._index_file(
                    file_path,
                    workspace_root=workspace_root,
                    owner_id=owner_id,
                )
            except Exception as exc:
                source = self._mark_failed_file(
                    file_path,
                    workspace_root=workspace_root,
                    owner_id=owner_id,
                    error=str(exc),
                )
            else:
                if source.status == "failed":
                    summary.failed += 1
                elif changed:
                    summary.indexed += 1
                else:
                    summary.skipped += 1
            summary.sources.append(self._source_model(source))
            if source.status == "failed":
                summary.failed += 1
        summary.failed = len([source for source in summary.sources if source.status == "failed"])
        return summary

    async def index_file(
        self,
        file_path: Path,
        *,
        workspace_root: str,
        owner_id: str = "local-user",
        relative_path: str | None = None,
    ) -> RAGSource:
        source, _changed = await self._index_file(
            file_path,
            workspace_root=workspace_root,
            owner_id=owner_id,
            relative_path=relative_path,
        )
        return self._source_model(source)

    async def query(
        self,
        query: str,
        *,
        top_k: int | None = None,
        owner_id: str = "local-user",
        owner_ids: Sequence[str] | None = None,
        prefer_owner_context: bool = False,
        context_limit: int | None = None,
    ) -> RAGQueryResult:
        normalized_query = query.strip()
        if not normalized_query:
            raise RAGServiceError("`query` is required.")
        scoped_owner_ids = self._owner_ids(owner_id=owner_id, owner_ids=owner_ids)
        citations = (
            self.sample_chunks(owner_id=scoped_owner_ids[0], limit=context_limit or top_k)
            if prefer_owner_context and scoped_owner_ids and scoped_owner_ids[0] != "local-user"
            else self.search(normalized_query, top_k=top_k, owner_ids=scoped_owner_ids)
        )
        if not citations and scoped_owner_ids and scoped_owner_ids[0] != "local-user":
            citations = self.sample_chunks(owner_id=scoped_owner_ids[0], limit=top_k)
        raw_result: Any | None = None
        provider_error: str | None = None
        if self.settings.rag_enable_raganything_query and scoped_owner_ids == ["local-user"]:
            try:
                raw_result = await self._with_query_timeout(
                    self.provider.answer(normalized_query, mode="hybrid")
                )
            except Exception as exc:
                provider_error = str(exc)
            else:
                answer = self._stringify_provider_result(raw_result)
                if not self._is_empty_provider_answer(answer):
                    if citations:
                        answer = self._append_citations(answer, citations)
                    return RAGQueryResult(
                        answer=answer,
                        citations=citations,
                        provider=self.provider.name,
                        raw_result=raw_result,
                    )
        if not citations:
            answer = "The knowledge base does not contain relevant indexed content for this query."
            return RAGQueryResult(
                answer=answer,
                citations=[],
                provider=self.provider.name,
                raw_result={"provider_error": provider_error} if provider_error else None,
            )
        answer = await self._answer_from_citations(normalized_query, citations)
        if citations:
            answer = self._append_citations(answer, citations)
        return RAGQueryResult(
            answer=answer,
            citations=citations,
            provider=self.provider.name,
            raw_result={
                "query_backend": "local-citations",
                "provider_error": provider_error,
            }
            if provider_error
            else {"query_backend": "local-citations"},
        )

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        owner_id: str = "local-user",
        owner_ids: Sequence[str] | None = None,
    ) -> list[RAGChunkHit]:
        limit = top_k or self.settings.rag_top_k
        terms = self._tokenize(query)
        if not terms:
            return []
        hits: list[RAGChunkHit] = []
        for scoped_owner_id in self._owner_ids(owner_id=owner_id, owner_ids=owner_ids):
            stmt = (
                select(RAGChunkRecord, RAGSourceRecord)
                .join(RAGSourceRecord, RAGChunkRecord.source_id == RAGSourceRecord.id)
                .where(
                    RAGChunkRecord.owner_id == scoped_owner_id,
                    RAGSourceRecord.status == "indexed",
                )
            )
            owner_hits: list[RAGChunkHit] = []
            for chunk, source in self.session.execute(stmt).all():
                score = self._score_text(chunk.text, terms)
                if score <= 0:
                    continue
                owner_hits.append(
                    RAGChunkHit(
                        source_id=source.id,
                        source_path=source.file_path,
                        relative_path=source.relative_path,
                        chunk_id=chunk.id,
                        position=chunk.position,
                        page_idx=chunk.page_idx,
                        score=score,
                        text=chunk.text[:1200],
                    )
                )
            owner_hits.sort(key=lambda hit: hit.score, reverse=True)
            hits.extend(owner_hits[: max(limit - len(hits), 0)])
            if len(hits) >= limit:
                break
        return hits[:limit]

    def sample_chunks(
        self,
        *,
        owner_id: str,
        limit: int | None = None,
    ) -> list[RAGChunkHit]:
        max_items = limit or self.settings.rag_top_k
        stmt = (
            select(RAGChunkRecord, RAGSourceRecord)
            .join(RAGSourceRecord, RAGChunkRecord.source_id == RAGSourceRecord.id)
            .where(RAGChunkRecord.owner_id == owner_id, RAGSourceRecord.status == "indexed")
            .order_by(
                RAGSourceRecord.updated_at.desc(),
                RAGSourceRecord.relative_path.asc(),
                RAGChunkRecord.position.asc(),
            )
            .limit(max_items)
        )
        return [
            RAGChunkHit(
                source_id=source.id,
                source_path=source.file_path,
                relative_path=source.relative_path,
                chunk_id=chunk.id,
                position=chunk.position,
                page_idx=chunk.page_idx,
                score=0.0,
                text=chunk.text[:1200],
            )
            for chunk, source in self.session.execute(stmt).all()
        ]

    def delete_source(self, source_id: str, *, owner_id: str = "local-user") -> bool:
        stmt = delete(RAGSourceRecord).where(
            RAGSourceRecord.id == source_id,
            RAGSourceRecord.owner_id == owner_id,
        )
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount > 0

    async def _index_file(
        self,
        file_path: Path,
        *,
        workspace_root: str,
        owner_id: str,
        relative_path: str | None = None,
    ) -> tuple[RAGSourceRecord, bool]:
        extension = file_path.suffix.lower()
        file_hash = self._hash_file(file_path)
        stat = file_path.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        source = self._get_or_create_source(
            file_path,
            workspace_root=workspace_root,
            owner_id=owner_id,
            relative_path=relative_path,
        )
        if source.status == "indexed" and source.file_hash == file_hash:
            return source, False

        source.status = "processing"
        source.error = None
        source.file_hash = file_hash
        source.modified_at = modified_at
        source.size_bytes = stat.st_size
        source.provider = self.provider.name
        source.updated_at = datetime.now(UTC)
        self.session.execute(delete(RAGChunkRecord).where(RAGChunkRecord.source_id == source.id))
        self.session.commit()

        try:
            if extension in OLD_OFFICE_EXTENSIONS:
                raise RAGServiceError(
                    "Legacy Office formats are not supported in v1. Convert this file to "
                    ".docx, .pptx, or PDF."
                )
            if extension == ".pdf":
                if self.settings.rag_pdf_parser.lower() == "mineru":
                    await self._index_pdf_with_mineru(file_path, source.doc_id)
                    content_list = self._extract_content_list(file_path)
                else:
                    try:
                        content_list = self._extract_content_list(file_path)
                    except Exception:
                        if not self.settings.rag_enable_mineru_fallback:
                            raise
                        await self._index_pdf_with_mineru(file_path, source.doc_id)
                        content_list = self._extract_content_list(file_path)
                    await self._maybe_insert_content_list(content_list, file_path, source.doc_id)
            else:
                content_list = self._extract_content_list(file_path)
                await self._maybe_insert_content_list(content_list, file_path, source.doc_id)
            self._replace_chunks(source, content_list, owner_id=owner_id)
            source.status = "indexed"
            source.indexed_at = datetime.now(UTC)
            source.error = None
        except Exception as exc:
            source.status = "failed"
            source.error = str(exc)
        finally:
            source.updated_at = datetime.now(UTC)
            self.session.add(source)
            self.session.commit()
            self.session.refresh(source)
        return source, True

    async def _maybe_insert_content_list(
        self,
        content_list: list[dict[str, Any]],
        file_path: Path,
        doc_id: str,
    ) -> None:
        if not self.settings.rag_enable_raganything_insert:
            return
        await self._with_index_timeout(
            self.provider.insert_content_list(
                content_list,
                file_path=file_path,
                doc_id=doc_id,
            )
        )

    async def _index_pdf_with_mineru(self, file_path: Path, doc_id: str) -> None:
        await self._with_index_timeout(
            self.provider.index_pdf(
                file_path,
                output_dir=Path(self.settings.rag_storage_dir) / "parsed",
                doc_id=doc_id,
            )
        )

    async def _with_index_timeout(self, awaitable):
        try:
            return await asyncio.wait_for(
                awaitable,
                timeout=max(int(self.settings.rag_index_timeout_seconds), 30),
            )
        except TimeoutError as exc:
            raise RAGProviderError(
                "RAG indexing timed out. For large or complex PDFs, try indexing a smaller "
                "folder first, or raise RAG_INDEX_TIMEOUT_SECONDS in `.env`."
            ) from exc

    async def _with_query_timeout(self, awaitable):
        try:
            return await asyncio.wait_for(
                awaitable,
                timeout=max(float(self.settings.rag_query_timeout_seconds), 0.1),
            )
        except TimeoutError as exc:
            raise RAGProviderError(
                "RAG-Anything query timed out. The local citation query fallback is still "
                "available; lower the folder size or keep RAG_ENABLE_RAGANYTHING_QUERY=false."
            ) from exc

    def _extract_content_list(self, file_path: Path) -> list[dict[str, Any]]:
        extension = file_path.suffix.lower()
        if extension in {".md", ".txt"}:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        elif extension == ".pdf":
            text = self._extract_pdf_markdown(file_path)
        else:
            text = self._convert_with_markitdown(file_path)
        chunks = self._chunk_text(text)
        if not chunks:
            raise RAGServiceError("No extractable text was found in this file.")
        return [{"type": "text", "text": chunk, "page_idx": 0} for chunk in chunks]

    def _extract_pdf_markdown(self, file_path: Path) -> str:
        text = self._extract_pdf_with_pymupdf4llm(file_path)
        if not text:
            text = self._extract_pdf_with_pypdf(file_path)
        if not text.strip():
            raise RAGServiceError(
                "No selectable text was found in this PDF. It may be scanned or image-only. "
                "Enable `RAG_ENABLE_MINERU_FALLBACK=true` or set `RAG_PDF_PARSER=mineru` "
                "to use OCR-style parsing."
            )
        return text

    def _extract_pdf_with_pymupdf4llm(self, file_path: Path) -> str:
        try:
            import pymupdf4llm
        except ImportError:
            return ""
        text = pymupdf4llm.to_markdown(str(file_path))
        if isinstance(text, list):
            text = "\n\n".join(str(item.get("text", "")) for item in text)
        return str(text)

    def _extract_pdf_with_pypdf(self, file_path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RAGServiceError(
                "Fast PDF indexing requires `pymupdf4llm` or `pypdf`. Run `uv sync`, "
                "or set `RAG_PDF_PARSER=mineru` to use the slower MinerU parser."
            ) from exc
        reader = PdfReader(str(file_path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"## Page {index}\n\n{text.strip()}")
        return "\n\n".join(pages)

    def _convert_with_markitdown(self, file_path: Path) -> str:
        if MarkItDown is None:
            raise RAGServiceError("MarkItDown is not installed, so this file cannot be parsed.")
        result = MarkItDown().convert(str(file_path))
        return result.text_content or ""

    def _replace_chunks(
        self,
        source: RAGSourceRecord,
        content_list: list[dict[str, Any]],
        *,
        owner_id: str,
    ) -> None:
        records = []
        for index, item in enumerate(content_list, start=1):
            text = self._content_item_text(item).strip()
            if not text:
                continue
            records.append(
                RAGChunkRecord(
                    owner_id=owner_id,
                    source_id=source.id,
                    position=index,
                    text=text,
                    page_idx=item.get("page_idx"),
                    extra={key: value for key, value in item.items() if key not in {"text"}},
                )
            )
        self.session.add_all(records)

    def _content_item_text(self, item: dict[str, Any]) -> str:
        if item.get("type") == "table":
            return str(item.get("table_body", ""))
        if item.get("type") == "equation":
            return " ".join(str(item.get(key, "")) for key in ("latex", "text")).strip()
        return str(item.get("text") or item.get("content") or "")

    def _chunk_text(self, text: str) -> list[str]:
        chunk_size = max(int(self.settings.rag_chunk_size), 300)
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(paragraph) > chunk_size:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(
                    paragraph[index : index + chunk_size]
                    for index in range(0, len(paragraph), chunk_size)
                )
                continue
            next_text = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(next_text) > chunk_size and current:
                chunks.append(current)
                current = paragraph
            else:
                current = next_text
        if current:
            chunks.append(current)
        return chunks

    def _iter_files(
        self,
        base: Path,
        *,
        recursive: bool,
        allowed_extensions: set[str],
    ) -> list[Path]:
        pattern = "**/*" if recursive else "*"
        return sorted(
            path
            for path in base.glob(pattern)
            if path.is_file() and path.suffix.lower() in allowed_extensions
        )

    def _normalize_extensions(self, extensions: list[str] | None) -> set[str]:
        configured = extensions or self.settings.rag_allowed_extensions
        normalized = {
            extension.lower() if extension.startswith(".") else f".{extension.lower()}"
            for extension in configured
        }
        return normalized & SUPPORTED_EXTENSIONS

    def _workspace_root(self, workspace_root: str) -> Path:
        if not workspace_root:
            raise RAGServiceError("`workspace_root` is required for local RAG indexing.")
        root = Path(workspace_root).expanduser()
        try:
            resolved = root.resolve(strict=True)
        except FileNotFoundError as exc:
            raise RAGServiceError(f"Workspace root `{workspace_root}` does not exist.") from exc
        if not resolved.is_dir():
            raise RAGServiceError(f"Workspace root `{workspace_root}` is not a directory.")
        return resolved

    def _resolve_path(self, workspace_root: str, requested_path: str) -> Path:
        root = self._workspace_root(workspace_root)
        raw = Path(requested_path).expanduser()
        candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise RAGServiceError("Requested path escapes the configured workspace root.") from exc
        return candidate

    def _get_or_create_source(
        self,
        file_path: Path,
        *,
        workspace_root: str,
        owner_id: str,
        relative_path: str | None = None,
    ) -> RAGSourceRecord:
        file_path_text = str(file_path)
        stmt = select(RAGSourceRecord).where(
            RAGSourceRecord.owner_id == owner_id,
            RAGSourceRecord.file_path == file_path_text,
        )
        source = self.session.execute(stmt).scalar_one_or_none()
        if source is not None:
            if relative_path and source.relative_path != relative_path:
                source.relative_path = relative_path
                self.session.add(source)
                self.session.commit()
                self.session.refresh(source)
            return source
        display_path = (
            relative_path or file_path.relative_to(self._workspace_root(workspace_root)).as_posix()
        )
        source = RAGSourceRecord(
            owner_id=owner_id,
            file_path=file_path_text,
            relative_path=display_path,
            extension=file_path.suffix.lower(),
            provider=self.provider.name,
            doc_id=f"local-{hashlib.sha1(file_path_text.encode('utf-8')).hexdigest()}",
        )
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

    def _owner_ids(
        self,
        *,
        owner_id: str = "local-user",
        owner_ids: Sequence[str] | None = None,
    ) -> list[str]:
        raw_owner_ids = list(owner_ids) if owner_ids is not None else [owner_id]
        scoped: list[str] = []
        seen: set[str] = set()
        for raw_owner_id in raw_owner_ids:
            candidate = str(raw_owner_id or "").strip()
            if not candidate or candidate in seen:
                continue
            scoped.append(candidate)
            seen.add(candidate)
        return scoped or ["local-user"]

    def _mark_failed_file(
        self,
        file_path: Path,
        *,
        workspace_root: str,
        owner_id: str,
        error: str,
    ) -> RAGSourceRecord:
        source = self._get_or_create_source(
            file_path,
            workspace_root=workspace_root,
            owner_id=owner_id,
        )
        source.status = "failed"
        source.error = error
        source.updated_at = datetime.now(UTC)
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

    def _source_model(self, record: RAGSourceRecord) -> RAGSource:
        return RAGSource.model_validate(
            {
                "id": record.id,
                "file_path": record.file_path,
                "relative_path": record.relative_path,
                "extension": record.extension,
                "file_hash": record.file_hash,
                "modified_at": record.modified_at,
                "size_bytes": record.size_bytes,
                "status": record.status,
                "error": record.error,
                "provider": record.provider,
                "doc_id": record.doc_id,
                "indexed_at": record.indexed_at,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
        )

    def _hash_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _tokenize(self, text: str) -> list[str]:
        return [term.lower() for term in _WORD_RE.findall(text) if len(term.strip()) >= 2]

    def _score_text(self, text: str, terms: list[str]) -> float:
        haystack = text.lower()
        score = 0.0
        for term in terms:
            score += haystack.count(term)
            if term in haystack:
                score += 0.5
        return score / max(len(text), 1) * 1000

    def _stringify_provider_result(self, raw_result: Any) -> str:
        if raw_result is None:
            return ""
        if isinstance(raw_result, str):
            return raw_result
        if isinstance(raw_result, dict):
            for key in ("answer", "result", "response", "content"):
                if key in raw_result:
                    return str(raw_result[key])
        return str(raw_result)

    def _is_empty_provider_answer(self, answer: str) -> bool:
        return answer.strip().lower() in {"", "none", "null"}

    async def _answer_from_citations(self, query: str, citations: list[RAGChunkHit]) -> str:
        context = "\n\n".join(
            f"[{index}] {hit.relative_path} chunk {hit.position}\n{hit.text}"
            for index, hit in enumerate(citations, start=1)
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "Answer the user's question using only the provided knowledge base "
                    "context. If the context is insufficient, say so briefly."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {query}\n\nKnowledge base context:\n{context}",
            },
        ]
        try:
            return await asyncio.wait_for(
                LLMService().generate_chat(messages),
                timeout=max(int(self.settings.api_timeout), 10),
            )
        except Exception:
            first = citations[0]
            return (
                "The knowledge base contains a matching passage, but answer generation failed. "
                f"Most relevant excerpt: {first.text[:500]}"
            )

    def _append_citations(self, answer: str, citations: list[RAGChunkHit]) -> str:
        lines = [answer.rstrip(), "", "Sources:"]
        seen: set[str] = set()
        for index, hit in enumerate(citations, start=1):
            key = f"{hit.relative_path}:{hit.position}"
            if key in seen:
                continue
            seen.add(key)
            page = f", page {hit.page_idx + 1}" if hit.page_idx is not None else ""
            lines.append(f"[{index}] {hit.relative_path} chunk {hit.position}{page}")
        return "\n".join(lines).strip()
