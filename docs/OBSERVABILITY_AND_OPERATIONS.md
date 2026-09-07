# Stage 4 — Observability, Delivery, and Production-Style Hardening

Stage 4 does **not** turn the demo into a production SRE platform. It adds the
engineering controls that make the existing agent workflow measurable,
traceable, reproducible, and easier to operate.

## 4A. Local observability

The API exposes Prometheus-format metrics at `GET /metrics` and emits JSON-lines
application events to stdout.

Key metric families:

- `incident_commander_http_requests_total`
- `incident_commander_http_request_duration_seconds`
- `incident_commander_workflow_runs_total`
- `incident_commander_workflow_duration_seconds`
- `incident_commander_agent_runs_total`
- `incident_commander_agent_duration_seconds`
- `incident_commander_mcp_tool_requests_total`
- `incident_commander_mcp_tool_results_total`
- `incident_commander_rag_retrievals_total`
- `incident_commander_rag_retrieval_duration_seconds`
- `incident_commander_hitl_decisions_total`
- `incident_commander_remediation_results_total`
- `incident_commander_safety_blocks_total`

Prometheus labels intentionally avoid `thread_id` to prevent high-cardinality
metrics. Thread IDs remain available in structured logs and durable checkpoint
history.

Every HTTP response also receives `X-Request-ID`, allowing API requests to be
correlated with JSON logs.

## 4B. LangSmith tracing

Tracing is optional and disabled by default. The application adds useful
LangGraph run names, tags, and metadata, and decorates custom runbook retrieval
and trusted MCP execution so those operations can appear in traces.

Set:

```text
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<key>
LANGSMITH_PROJECT=agentic-incident-commander
```

The API never returns or logs the API key.

Because tracing can send prompts, tool inputs, outputs, and state to an external
service, keep it disabled for data that should remain local unless the tracing
policy explicitly allows that data.

## 4C. Docker hardening

The Dockerfile now uses a builder/runtime split, installs the built wheel into a
small Python runtime, creates a non-root application user, adds a healthcheck,
and uses one Uvicorn worker for the local SQLite-backed deployment.

`compose.yaml` persists `data/` and connects the container to an Ollama instance
running on the host through `host.docker.internal`.

SQLite remains a local/single-instance choice. A multi-replica production
system should use a production-grade shared checkpoint backend rather than
scaling this container horizontally with the same local SQLite file.

## 4D. CI and measurable evaluation

`.github/workflows/ci.yml` runs on pushes and pull requests to `main` for Python
3.11 and 3.12. It performs:

1. editable install with development dependencies,
2. Ruff linting,
3. Pytest,
4. coverage collection with a 50% minimum,
5. coverage XML artifact upload,
6. Docker image build, container startup, and `/health` smoke verification.

The CI suite explicitly uses deterministic agents and lexical retrieval, so it
does not require Ollama, cloud API keys, or external model services.

A separate release workflow publishes the container to GHCR when a GitHub
Release is published. This provides a continuous-delivery path without storing
a separate registry password; it uses the repository-scoped `GITHUB_TOKEN`.

The Stage 3 golden evaluation is also extended with end-to-end latency and tool
request counts. It now reports mean, p50, and p95 workflow latency. These values
must be measured on the user's machine before they are used on a resume.

## Safety invariants preserved

Stage 4 does not relax the remediation boundary:

- state-changing actions still require LangGraph HITL approval,
- the trusted executor still checks approval again,
- the remediation tool still refuses calls without approval,
- the action allow-list remains enforced,
- remediation remains simulation-only.
