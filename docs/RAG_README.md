# Local Knowledge Base RAG

This project uses RAG-Anything as the primary local knowledge-base backend, with a
small wrapper for common student materials. The first version is intentionally
text-first: PDF, Markdown, text, DOCX, and PPTX. It does not require LibreOffice.

## Setup

Install backend dependencies after pulling the branch:

```bash
uv sync
```

`raganything` is declared in `pyproject.toml`, so `uv sync` installs it into the
project environment. If it is missing, RAG API calls return a configuration error
instead of silently succeeding.

RAG-Anything uses the same chat LLM configuration that the app already uses for
answer generation. Configure an OpenAI-compatible LLM profile in the app settings
for the current backend process, or provide these environment variables in `.env`
for team/restart-safe setup:

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-api-key
LLM_BASE_URL=optional-openai-compatible-base-url
RAG_EMBEDDING_PROVIDER=local
RAG_EMBEDDING_DIM=1536
RAG_PDF_PARSER=fast
RAG_ENABLE_MINERU_FALLBACK=false
RAG_ENABLE_RAGANYTHING_INSERT=false
RAG_ENABLE_RAGANYTHING_QUERY=false
RAG_STORAGE_DIR=./data/rag
RAG_INDEX_TIMEOUT_SECONDS=180
RAG_QUERY_TIMEOUT_SECONDS=20
```

If the backend is restarted and the key only existed in the in-app Settings
screen, enter it again or move it to `.env`.

`RAG_EMBEDDING_PROVIDER=local` is the default. It uses a deterministic local hash
embedding so DeepSeek-style chat profiles can index documents even when the chat
API does not provide an embeddings endpoint. If your team has a working
OpenAI-compatible embeddings API, set:

```bash
RAG_EMBEDDING_PROVIDER=openai
RAG_EMBEDDING_MODEL=text-embedding-3-small
RAG_EMBEDDING_DIM=1536
```

By default, indexing uses laptop-friendly local chunks stored in the project
SQLite database, and answers are generated from those chunks with the same chat
LLM profile. This keeps class notes and school PDFs usable without running
LightRAG graph extraction for every file.

`RAG_ENABLE_RAGANYTHING_INSERT=true` opts into RAG-Anything/LightRAG insertion
after text extraction. This can be useful for deeper experiments, but it may be
slow because LightRAG can call the chat model while building its graph storage.

`RAG_ENABLE_RAGANYTHING_QUERY=true` opts into RAG-Anything query first, with
local citation answering as fallback. `RAG_QUERY_TIMEOUT_SECONDS` limits that
provider query before fallback.

`RAG_INDEX_TIMEOUT_SECONDS` controls how long one file may spend in the optional
RAG-Anything insertion path before the source is marked failed.

## Running Locally

Backend:

```bash
uv run uvicorn backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`, go to the file panel, enter a local folder path in
`Knowledge folder`, then click `Index`.

## Folder Rules

The folder path you enter is treated as the approved workspace root for that
indexing run. The backend only reads files inside that folder. Original files are
not copied or moved.

Index data is stored under:

```text
./data/rag
```

The SQLite database stores source metadata, status, hashes, and searchable text
chunks. RAG-Anything stores its working index under `./data/rag/raganything` only
when `RAG_ENABLE_RAGANYTHING_INSERT=true` or `RAG_ENABLE_RAGANYTHING_QUERY=true`.

## Supported Files

Supported in v1:

- `.pdf`: defaults to fast local text extraction. PyMuPDF4LLM is preferred when
  installed; otherwise the service falls back to pypdf text extraction. The
  resulting text is stored as local searchable chunks. Text PDFs are the main
  target.
- `.md`, `.txt`: read directly and stored as local searchable chunks.
- `.docx`, `.pptx`: converted with MarkItDown, then stored as local searchable
  chunks.

Not supported in v1:

- `.doc`, `.ppt`: convert these to `.docx`, `.pptx`, or PDF.
- Scanned PDFs and image-only formulas: not handled by the default fast parser.
  Set `RAG_PDF_PARSER=mineru` or `RAG_ENABLE_MINERU_FALLBACK=true` only when
  you explicitly need OCR-style parsing and can tolerate slow local inference.

## Readiness Check

Use the status endpoint before indexing:

```bash
curl http://127.0.0.1:8000/api/rag/status
```

The response must have `ready: true`. If `ready` is false, fix the listed
`issues` first, usually by running `uv sync` or configuring `LLM_API_KEY`.

## Why Indexing Can Be Slow

With the default settings, text extraction and local chunk storage should stay
practical on a laptop. MinerU is much slower because it can run transformer/VLM
document analysis locally; keep it off unless a PDF is scanned or image-heavy.
RAG-Anything/LightRAG insertion can also be slow because it may call the chat
model to build graph storage, so it is disabled by default for v1. If
`RAG_EMBEDDING_PROVIDER=openai`, optional RAG-Anything insertion also calls the
configured embedding endpoint. For a quick smoke test, start with a folder
containing one small `.md` or `.txt` file.

If a source stays in `processing` for too long, restart the backend and retry with
a smaller folder or raise `RAG_INDEX_TIMEOUT_SECONDS`.

## API

- `POST /api/rag/index-folder`
- `GET /api/rag/sources`
- `POST /api/rag/query`
- `DELETE /api/rag/sources/{source_id}`

The agent also has these tools:

- `rag_index_folder`
- `rag_search`
- `rag_answer`
