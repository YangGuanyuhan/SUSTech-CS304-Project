# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11

# -------------------------
# Stage 1: Dependencies
# -------------------------
FROM python:${PYTHON_VERSION}-slim AS deps
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency manifests
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# -------------------------
# Stage 2: Final runtime
# -------------------------
FROM python:${PYTHON_VERSION}-slim AS final
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy virtual environment
COPY --from=deps /app/.venv /app/.venv

# Copy application code
COPY backend/ ./backend/

# Prepare data directory
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

USER appuser

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
