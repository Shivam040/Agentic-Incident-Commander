# Agentic Incident Commander — v0.4

A portfolio-grade Agentic AI incident-response system demonstrating:

- LangGraph workflow orchestration
- LangChain specialist agents
- FastMCP tool integration and genuine LLM tool calling
- structured RCA and remediation output
- human-in-the-loop remediation approval
- durable SQLite LangGraph checkpoints
- semantic vector RAG over operational runbooks
- golden-set evaluation with reliability/safety metrics
- **Prometheus metrics + structured JSON logs**
- **optional LangSmith end-to-end tracing**
- **hardened Docker/Compose runtime**
- **GitHub Actions CI with lint, tests, and coverage**
- local/free Ollama development

## Architecture

```text
Incident/API request
      |
      +------------------> JSON logs + Prometheus metrics
      |
      v
LangGraph Supervisor
      |
      v
Telemetry Agent (LLM)
      |--- MCP metrics()
      |--- MCP logs()
      |
      v
Structured RCA Agent
      |
      v
Runbook Agent (LLM)
      |--- MCP runbook_search()
      |        |
      |        +-- nomic-embed-text
      |        +-- persistent vector index
      |
      v
Remediation Planner
      |
      v
LangGraph interrupt()
      |
      +---- reject/no_action ---> Report
      |
      +---- approve -----------> trusted MCP remediate() ---> Report

State/checkpoints ---> SQLite
Optional traces ----> LangSmith
CI ----------------> Ruff + Pytest + coverage on Python 3.11/3.12
```

## Verified Stage 3 baseline

Before Stage 4 changes, the local 8-case golden evaluation completed 8/8 runs
and reported 100% for telemetry tool calling, runbook tool calling, RCA keyword
match, action selection, HITL gating, runbook hit rate, semantic-vector usage,
and safety compliance. Treat this as an **8-case local evaluation**, not as a
production benchmark.

## Setup

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

Run the API:

```powershell
$env:AI_MODE="llm"
$env:AI_PROVIDER="ollama"
$env:OLLAMA_MODEL="qwen3:4b"
$env:RUNBOOK_RETRIEVAL="semantic"
uvicorn incident_commander.api:app
```

Open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/health
http://127.0.0.1:8000/metrics
```

## Stage 4A — verify local observability

No LLM is required for this smoke test:

```powershell
python scripts/smoke_observability.py
```

Expected:

```text
Stage 4A observability smoke test: PASS
```

The API produces JSON log lines containing fields such as `event`,
`request_id`, `thread_id`, `service`, `status`, and `duration_ms`. Metrics avoid
thread IDs as labels to keep cardinality bounded.

## Stage 4B — enable LangSmith tracing

Tracing is deliberately off by default. After creating a LangSmith API key:

```powershell
$env:LANGSMITH_TRACING="true"
$env:LANGSMITH_API_KEY="<your-key>"
$env:LANGSMITH_PROJECT="agentic-incident-commander"
uvicorn incident_commander.api:app
```

Create an incident or run the evaluation, then inspect the configured LangSmith
project. The graph invocation carries run names, service tags, case metadata,
custom runbook retrieval spans, and trusted MCP execution spans.

Do not commit `.env` or API keys.

## Stage 4C — Docker

Ollama should be running on the host with both models pulled.

```powershell
docker compose build
docker compose up
```

The container runs as a non-root user and includes a Docker healthcheck. The
Compose configuration persists `data/` so SQLite checkpoints and the local
vector index survive container recreation.

## Stage 4D — CI/CD

The repository includes:

```text
.github/workflows/ci.yml
```

On pushes/pull requests to `main`, GitHub Actions tests Python 3.11 and 3.12,
runs Ruff, executes Pytest with coverage, enforces a 50% coverage floor,
uploads `coverage.xml`, builds the Docker image, starts a deterministic
container, and verifies its `/health` endpoint.

CI uses:

```text
AI_MODE=deterministic
RUNBOOK_RETRIEVAL=lexical
LANGSMITH_TRACING=false
RUN_LLM_TESTS=0
```

so CI does not depend on Ollama or secrets.

The repository also includes `.github/workflows/release.yml`. Publishing a
GitHub Release builds the same Dockerfile and delivers the image to GitHub
Container Registry (GHCR) using the repository `GITHUB_TOKEN`. Verify at least
one successful release run before describing the delivery workflow as proven.

## Golden evaluation + performance metrics

Run the real local LLM evaluation:

```powershell
$env:AI_MODE="llm"
$env:RUNBOOK_RETRIEVAL="semantic"
python scripts/evaluate_agent.py
```

In addition to the Stage 3 quality/safety metrics, v0.4 records:

- run success rate
- mean end-to-end incident latency
- p50 end-to-end incident latency
- p95 end-to-end incident latency
- mean tool requests per incident
- unsafe execution rate

The output is written to:

```text
evaluations/latest_results.json
```

Use latency numbers on a resume only after measuring them on your own machine.

## API

```text
GET  /health
GET  /metrics
POST /incidents
POST /incidents/{thread_id}/decision
GET  /incidents/{thread_id}
GET  /incidents/{thread_id}/history
```

## Resume-safe claims after Stage 4 verification

Once the Stage 4 smoke test, CI, Docker healthcheck, and optional LangSmith trace
have been verified on your setup, defensible claims include:

> Engineered an observable LangGraph-based agentic incident-response system
> with MCP tool calling, semantic RAG, durable HITL checkpoints, Prometheus
> metrics, structured logging, optional LangSmith tracing, containerized
> deployment, and automated CI testing.

Do not claim Kubernetes/AKS, distributed production persistence, real service
remediation, or production SLO improvements; those are not implemented here.

See `docs/STAGE4_ARCHITECTURE.md` for design details.
