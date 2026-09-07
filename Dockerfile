# syntax=docker/dockerfile:1

# ---------- Build stage ----------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Copy dependency metadata and source needed to build the package wheel.
COPY pyproject.toml README.md ./
COPY src ./src

# Build wheels once so the runtime image does not need build tooling.
RUN python -m pip wheel --wheel-dir /wheels .


# ---------- Runtime stage ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AI_MODE=llm \
    AI_PROVIDER=ollama \
    OLLAMA_MODEL=qwen3:4b \
    OLLAMA_EMBEDDING_MODEL=nomic-embed-text \
    OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    RUNBOOK_RETRIEVAL=semantic \
    RUNBOOK_VECTOR_INDEX_PATH=/app/data/vector_index/runbooks.json \
    CHECKPOINT_DB_PATH=/app/data/checkpoints/incident_commander.sqlite \
    LANGGRAPH_STRICT_MSGPACK=true \
    LOG_LEVEL=INFO

WORKDIR /app

# Dedicated unprivileged runtime identity.
RUN addgroup --system app \
    && adduser --system --ingroup app --home /nonexistent --no-create-home app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# Operational data is baked into the image; only checkpoint/vector subdirectories
# are mounted as writable named volumes by Compose.
COPY --chown=app:app data ./data
COPY --chown=app:app evaluations ./evaluations
COPY --chown=app:app docs ./docs
COPY --chown=app:app NOTICE.md README.md ./

RUN mkdir -p /app/data/checkpoints /app/data/vector_index \
    && chown -R app:app /app/data /app/evaluations

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# One worker is intentional for this SQLite-backed local portfolio deployment.
# Scaling to multiple workers should use an external/shared checkpoint store.
CMD ["uvicorn", "incident_commander.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
