# Stage 4C — Docker hardening patch

Copy these files into the root of the current Agentic Incident Commander project:

- `Dockerfile`
- `compose.yaml`
- `.dockerignore`
- `.env.docker.example`
- `scripts/smoke_docker.ps1`

This patch intentionally does **not** replace application code, runbooks, telemetry,
evaluation cases, prompts, or your 30-case benchmark changes.

## What it adds

- multi-stage Python 3.12 build
- dependency wheels built outside runtime stage
- dedicated non-root `app` user
- one Uvicorn worker for the SQLite-backed local deployment
- Docker healthcheck
- persistent named volumes for LangGraph checkpoints and vector index
- host Ollama access through `host.docker.internal:11434`
- read-only container root filesystem
- writable `/tmp` tmpfs
- all Linux capabilities dropped
- `no-new-privileges`
- init process and graceful shutdown window
- optional LangSmith variables passed at runtime, not baked into the image
- runtime SQLite/vector artifacts excluded from the image build context

## Validate

Make sure Docker Desktop and Ollama are running, and that these models exist:

```powershell
ollama list
```

Then:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\smoke_docker.ps1
```

Or manually:

```powershell
docker compose config
docker compose build
docker compose up -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing
docker compose logs --tail=100
```

## Reset persistent local state

Only if you intentionally want to delete Docker checkpoint/vector state:

```powershell
docker compose down -v
```

Normal stop/restart should use:

```powershell
docker compose down
docker compose up -d
```

which preserves the named volumes.
