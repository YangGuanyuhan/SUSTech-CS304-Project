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

RAG-Anything needs the same OpenAI-compatible API key for both completion and
embeddings. Configure an OpenAI-compatible LLM profile in the app settings for
the current backend process, or provide these environment variables in `.env` for
team/restart-safe setup:

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-api-key
LLM_BASE_URL=optional-openai-compatible-base-url
RAG_EMBEDDING_MODEL=text-embedding-3-small
RAG_EMBEDDING_DIM=1536
RAG_STORAGE_DIR=./data/rag
RAG_INDEX_TIMEOUT_SECONDS=180
```

If the backend is restarted and the key only existed in the in-app Settings
screen, enter it again or move it to `.env`.

`RAG_INDEX_TIMEOUT_SECONDS` controls how long one file may spend inside
RAG-Anything indexing before the source is marked failed.

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

The SQLite database stores source metadata, status, hashes, and lightweight chunk
citations. RAG-Anything stores its working index under `./data/rag/raganything`.

## Supported Files

Supported in v1:

- `.pdf`: indexed through RAG-Anything. Text PDFs are the main target.
- `.md`, `.txt`: read directly and inserted into RAG-Anything as content lists.
- `.docx`, `.pptx`: converted with MarkItDown, then inserted as content lists.

Not supported in v1:

- `.doc`, `.ppt`: convert these to `.docx`, `.pptx`, or PDF.
- Scanned PDFs and image-only formulas: may be slow or low quality unless the
  RAG-Anything parser/OCR stack is fully configured.

## Readiness Check

Use the status endpoint before indexing:

```bash
curl http://127.0.0.1:8000/api/rag/status
```

The response must have `ready: true`. If `ready` is false, fix the listed
`issues` first, usually by running `uv sync` or configuring `LLM_API_KEY`.

## Why Indexing Can Be Slow

RAG-Anything may initialize MinerU, parse PDFs, build LightRAG storage, and call
the configured LLM/embedding endpoint. The first PDF on a fresh machine can be
especially slow. PDF parsing can also download MinerU parser models from
HuggingFace; if that download times out, the PDF source fails. For a quick smoke
test, start with a folder containing one small `.md` or `.txt` file.

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
