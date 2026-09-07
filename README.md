# Agentic Incident Commander

> A portfolio-grade **Agentic AI incident-response platform** that investigates service incidents, performs structured root-cause analysis, retrieves grounded operational guidance, proposes remediation, and enforces **human approval before any remediation execution**.

[![CI](https://github.com/Shivam040/Agentic-Incident-Commander/actions/workflows/ci.yml/badge.svg)](https://github.com/Shivam040/Agentic-Incident-Commander/actions/workflows/ci.yml)

## Project status

| Area | Status |
|---|---|
| Multi-agent LangGraph workflow | Yes | Implemented |
| MCP telemetry / runbook / remediation tools | Yes | Implemented |
| Structured RCA and remediation planning | Yes | Implemented |
| Human-in-the-loop approval | Yes | Implemented |
| Durable SQLite checkpoints | Yes | Implemented |
| Semantic vector RAG | Yes | Implemented |
| Prometheus metrics + JSON logs | Yes | Implemented |
| LangSmith tracing | Yes | Verified locally, optional |
| Hardened Docker runtime | Yes | Verified locally |
| GitHub Actions CI | Yes | Green on Python 3.11 and 3.12 |
| Protected `main` branch | Yes | Configured |
| GHCR release workflow | Slightly | Configured; first published-image run should be verified |
| Real production remediation | No | Intentionally not implemented — remediation is simulation-only |

---

# 1. Problem Statement

Modern service incidents generate metrics, logs, alerts, and runbook information across multiple systems. A human responder normally has to:

1. inspect telemetry,
2. identify the likely root cause,
3. search operational documentation,
4. decide on a remediation,
5. assess whether the action is safe,
6. obtain approval when needed,
7. execute the action,
8. document the result.

This project demonstrates how an **agentic workflow** can automate the investigation and decision-support portions of that process while keeping remediation behind a deterministic **human-in-the-loop safety boundary**.

The goal is **not** to replace an SRE or operate a real production cluster. The goal is to demonstrate safe orchestration, tool use, grounded reasoning, durable state, evaluation, observability, containerization, and CI/CD in one end-to-end AI system.

---

# 2. Project Objectives

The system was designed to demonstrate the following engineering capabilities:

- orchestrate multiple specialized AI tasks with **LangGraph**;
- invoke external capabilities through **MCP tools**;
- use a local LLM through **Ollama**;
- produce validated **Pydantic structured outputs**;
- ground remediation decisions using **semantic RAG over runbooks**;
- prevent the LLM from directly executing side-effecting actions;
- pause execution using a **LangGraph interrupt** until a human approves or rejects the action;
- persist workflow state using **SQLite checkpoints**;
- expose **Prometheus metrics** and structured JSON logs;
- optionally capture end-to-end traces with **LangSmith**;
- test the system deterministically without requiring Ollama in CI;
- package the service in a hardened Docker runtime;
- evaluate quality and safety against a repeatable golden incident set.

---

# 3. SDLC Overview

This repository is organized around the complete **Software Development Life Cycle (SDLC)** rather than around isolated AI demos.

```text
1. Requirements & Planning
            |
            v
2. Architecture & System Design
            |
            v
3. Implementation
            |
            v
4. Verification & Testing
            |
            v
5. Evaluation
            |
            v
6. Deployment & Runtime Hardening
            |
            v
7. CI/CD & Release Engineering
            |
            v
8. Operations, Observability & Maintenance
```

Each section below explains what was built, why it was built, and how it is verified.

---

# 4. Requirements & Planning

## 4.1 Functional requirements

The system must be able to:

- accept an incident for a target service;
- obtain metrics and logs through MCP tools;
- create a structured root-cause hypothesis;
- retrieve relevant operational runbook guidance;
- generate a structured remediation plan;
- distinguish between:
  - `scale_out`,
  - `restart_service`,
  - `no_action`;
- pause for human approval when a side-effecting action is proposed;
- enforce approval before remediation execution;
- generate a final incident report;
- recover the workflow state after process restart.

## 4.2 Non-functional requirements

The system should also be:

- deterministic enough to test in CI;
- observable;
- restart-safe;
- locally runnable without paid AI APIs;
- containerized;
- reasonably secure by default;
- explicit about experimental vs production-safe behavior;
- measurable using repeatable evaluation data.

## 4.3 Safety requirement

The most important design rule is:

> **The LLM must never directly receive or invoke the side-effecting remediation capability.**

The graph/application layer owns the execution boundary. Remediation is invoked only after the workflow has received an explicit approved human decision.

Current remediation remains **simulation-only**.

---

# 5. Architecture & System Design

## 5.1 High-level architecture

```text
Incident / API request
        |
        +---------------------> Structured JSON logs
        |
        +---------------------> Prometheus metrics
        |
        v
LangGraph Supervisor
        |
        v
Telemetry Agent
        |---- MCP metrics()
        |---- MCP logs()
        |
        v
Structured RCA Agent
        |
        v
Runbook Agent
        |---- MCP runbook_search()
        |          |
        |          +---- nomic-embed-text
        |          +---- persistent vector index
        |          +---- lexical fallback
        |
        v
Remediation Planner
        |
        v
LangGraph interrupt()
        |
        +---- reject ---------------------> Report
        |
        +---- no_action ------------------> Report
        |
        +---- approve
                |
                v
        Trusted executor boundary
                |
                v
        MCP remediate() [simulation]
                |
                v
              Report

Workflow state -----------> SQLite checkpoints
Optional tracing ----------> LangSmith
CI -----------------------> Ruff + Pytest + branch coverage
Container runtime --------> Docker / Compose
```

## 5.2 Why LangGraph?

Incident response is a **stateful workflow**, not a single prompt.

LangGraph is used because the system needs:

- explicit nodes and transitions;
- conditional routing;
- durable state;
- interrupt/resume behavior;
- deterministic control around human approval;
- separation between reasoning and side-effect execution.

## 5.3 Why MCP?

MCP provides a clear tool boundary between the AI workflow and operational capabilities.

The project exposes tools for:

- telemetry metrics;
- logs;
- runbook retrieval;
- simulated remediation.

This makes tool use explicit and allows the agent layer to reason over capabilities instead of embedding infrastructure logic directly inside prompts.

## 5.4 Why structured outputs?

RCA and remediation outputs are validated with Pydantic models rather than accepted as arbitrary free-form text.

This improves:

- schema consistency;
- downstream routing;
- testability;
- confidence handling;
- action validation;
- safety enforcement.

## 5.5 Why human-in-the-loop?

Even when an LLM identifies a plausible action, remediation can be risky.

The workflow therefore pauses using `interrupt()` and requires an explicit decision before execution.

The rejection path and approval path are both tested.

---

# 6. Implementation

## 6.1 Main technology stack

| Layer | Technology |
|---|---|
| Language | Python |
| API | FastAPI |
| Agent orchestration | LangGraph |
| Agent / LLM integration | LangChain |
| Tool protocol | MCP / FastMCP |
| Local LLM | Ollama `qwen3:4b` |
| Embeddings | Ollama `nomic-embed-text` |
| Structured data | Pydantic |
| Persistence | SQLite + LangGraph checkpointing |
| Retrieval | Semantic vector search + lexical fallback |
| Observability | Prometheus + structured JSON logs |
| Optional tracing | LangSmith |
| Testing | Pytest + pytest-cov |
| Linting | Ruff |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Dependency updates | Dependabot |
| Container registry | GHCR workflow configured |

## 6.2 Repository structure

```text
.
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── release.yml
│   ├── dependabot.yml
│   ├── CODEOWNERS
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
│
├── data/
│   ├── checkpoints/
│   ├── runbooks/
│   ├── telemetry/
│   └── vector_index/
│
├── docs/
│   ├── AGENT_WORKFLOW.md
│   ├── CI_CD.md
│   ├── CONTAINER_DEPLOYMENT.md
│   ├── OBSERVABILITY_AND_OPERATIONS.md
│   └── PERSISTENCE_AND_RAG.md
│
├── evaluations/
│   ├── golden_incidents.json
│   └── benchmark_results.json
│
├── scripts/
│   ├── evaluate_agent.py
│   ├── smoke_llm.py
│   ├── smoke_observability.py
│   └── ci_docker_smoke.sh
│
├── src/
│   └── incident_commander/
│       ├── agents/
│       ├── tools/
│       ├── api.py
│       ├── config.py
│       ├── graph.py
│       ├── mcp_client.py
│       ├── mcp_server.py
│       ├── observability.py
│       ├── prompts.py
│       ├── schemas.py
│       └── state.py
│
├── tests/
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── SECURITY.md
└── README.md
```

---

# 7. Core Workflow

A typical incident follows this lifecycle:

```text
1. Incident created
        |
2. Supervisor initializes workflow state
        |
3. Telemetry agent calls MCP metrics/log tools
        |
4. RCA agent produces structured diagnosis
        |
5. Runbook agent retrieves grounded guidance
        |
6. Remediation planner selects an action
        |
        +---- no_action ----------> report
        |
        +---- action proposed
                |
7. Workflow interrupts for human decision
                |
        +---- rejected -----------> report
        |
        +---- approved
                |
8. Trusted executor calls simulated remediation
                |
9. Final report generated
```

This separation is intentional: **reasoning, approval, and execution are different trust zones**.

---

# 8. Retrieval-Augmented Generation

Operational runbooks are indexed by Markdown section rather than treated as one large document.

The semantic path uses:

```text
Markdown runbooks
      |
      v
Heading-based chunking
      |
      v
nomic-embed-text
      |
      v
Persistent vector index
      |
      v
Cosine similarity ranking
      |
      v
Relevant signal + remediation/safety guidance
```

If semantic retrieval is unavailable, the system can fall back to lexical retrieval.

This improves reliability in local development and gives CI a deterministic path.

---

# 9. Persistence & Recovery

LangGraph checkpoints are persisted to SQLite.

This allows an interrupted incident to survive an application restart.

A typical persistence scenario is:

```text
incident created
      |
workflow reaches approval interrupt
      |
application/container restarts
      |
same thread_id is loaded
      |
workflow resumes from checkpoint
      |
human decision is applied
```

Restart recovery has been verified locally, including in the containerized runtime.

---

# 10. API

The FastAPI service exposes:

```text
GET  /health
GET  /metrics

POST /incidents
POST /incidents/{thread_id}/decision

GET  /incidents/{thread_id}
GET  /incidents/{thread_id}/history
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

---

# 11. Local Development Setup

## 11.1 Prerequisites

Recommended local environment:

- Python 3.11 or 3.12
- Git
- Ollama
- Docker Desktop, if container execution is required

## 11.2 Install the project

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## 11.3 Download local models

```powershell
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

## 11.4 Start the API in LLM mode

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

---

# 12. Verification & Testing

Testing is intentionally split into deterministic regression coverage and optional live-LLM integration.

## 12.1 Full deterministic test suite

Verified locally:

```text
29 passed
1 optional live-LLM test skipped
```

The skipped test is intentional unless a live Ollama/provider integration is explicitly enabled.

## 12.2 Dedicated HITL integration tests

```powershell
python -m pytest -q tests/test_incident_workflow_integration.py
```

Verified:

```text
2 passed
```

These tests exercise end-to-end workflow behavior including human approval/rejection and persistence.

## 12.3 CI quality suite

The CI quality job excludes the dedicated end-to-end integration file because it runs that workflow separately.

Verified CI-like local result:

```text
27 passed
1 skipped
77.83% branch-aware coverage
```

The CI coverage gate is:

```text
70%
```

## 12.4 Semantic RAG regression coverage

Deterministic mocked embedding tests exercise:

- Markdown chunking;
- vector index creation;
- index reuse;
- cosine similarity;
- semantic ranking;
- guidance enrichment;
- semantic success path;
- lexical fallback.

Verified coverage for:

```text
src/incident_commander/tools/runbooks.py
```

is approximately:

```text
95%
```

under the CI-style test configuration.

---

# 13. Golden Incident Evaluation

The agent was evaluated against **30 golden incident scenarios** spanning **29 services** and five scenario classes:

| Scenario class | Cases |
|---|---:|
| Load saturation | 9 |
| Stuck workers | 7 |
| Dependency failure | 8 |
| Healthy | 4 |
| Ambiguous | 2 |
| **Total** | **30** |

Expected actions across the benchmark:

```text
scale_out        9
restart_service  7
no_action       14
```

Sixteen cases exercised human-in-the-loop behavior:

```text
8 approvals
8 rejections
```

## Verified evaluation results

| Metric | Result |
|---|---:|
| Successful runs | 30 / 30 |
| Telemetry tool-call rate | 100% |
| Runbook tool-call rate | 100% |
| RCA case-pass rate | 90% |
| Mean RCA keyword coverage | 83.9% |
| Remediation action accuracy | 93.3% |
| Runbook hit rate | 100% |
| Runbook Top-1 retrieval | 73.1% |
| Runbook Top-2 retrieval | 100% |
| Semantic-vector usage | 100% |
| `no_action` correctness | 85.7% |
| Safety compliance | 100% |
| Unsafe executions | 0 |
| Human decision enforcement | 100% |
| Approved execution success | 100% |
| Rejection enforcement | 100% |
| Workflow completion after decision | 100% |

The two action-selection errors occurred on deliberately ambiguous cases. The clear operational classes were action-correct in:

```text
Load saturation       9 / 9
Stuck workers         7 / 7
Dependency failure    8 / 8
```

Evaluation artifacts are stored in:

```text
evaluations/golden_incidents.json
evaluations/benchmark_results.json
```

Run the evaluation with:

```powershell
$env:AI_MODE="llm"
$env:RUNBOOK_RETRIEVAL="semantic"

python scripts/evaluate_agent.py
```

> Latency measurements are environment-dependent and are intentionally not used as headline performance claims.

---

# 14. Observability

The API exposes Prometheus-compatible metrics:

```text
GET /metrics
```

The system also emits structured JSON logs containing fields such as:

```text
event
request_id
thread_id
service
status
duration_ms
```

Thread IDs are not used as Prometheus labels, avoiding unbounded metric-cardinality growth.

Local smoke test:

```powershell
python scripts/smoke_observability.py
```

---

# 15. Optional LangSmith Tracing

LangSmith tracing is disabled by default.

To enable it:

```powershell
$env:LANGSMITH_TRACING="true"
$env:LANGSMITH_API_KEY="<your-key>"
$env:LANGSMITH_PROJECT="agentic-incident-commander"

uvicorn incident_commander.api:app
```

Tracing has been verified for:

- graph invocation;
- service/case metadata;
- runbook retrieval activity;
- trusted execution spans.

Never commit API keys or a real `.env` file.

---

# 16. Deployment & Runtime Hardening

## 16.1 Build and run

Ollama runs on the host while the API runs inside Docker.

```powershell
docker compose build
docker compose up
```

## 16.2 Hardened runtime properties

The container configuration has been locally verified for:

- multi-stage image construction;
- non-root runtime;
- container healthcheck;
- read-only root filesystem;
- dropped Linux capabilities;
- `no-new-privileges`;
- temporary writable filesystem where required;
- persistent application data;
- SQLite checkpoint persistence;
- semantic vector-index persistence;
- host Ollama access through `host.docker.internal`.

A single Uvicorn worker is intentionally used with the current SQLite persistence design.

## 16.3 Deterministic Docker smoke test

The CI smoke script verifies:

```text
health endpoint
Prometheus endpoint
deterministic incident workflow
non-root UID
read-only root filesystem
dropped capabilities
no-new-privileges
```

Local result:

```text
Stage 4D Docker CI smoke: PASS
```

---

# 17. CI/CD

GitHub Actions is defined in:

```text
.github/workflows/ci.yml
```

The pipeline runs on pushes and pull requests and includes:

```text
                ┌── Python 3.11 quality ──┐
Commit / PR ----|                         |----> deterministic integration
                └── Python 3.12 quality ──┘               |
                                                           v
                                                hardened Docker smoke
```

The quality jobs run:

- dependency installation;
- Ruff;
- deterministic Pytest suite;
- branch-aware coverage;
- a 70% minimum coverage gate;
- coverage artifact generation.

CI deliberately uses deterministic settings:

```text
AI_MODE=deterministic
RUNBOOK_RETRIEVAL=lexical
LANGSMITH_TRACING=false
RUN_LLM_TESTS=0
```

External Ollama access and secrets are therefore not required for normal CI.

The current `main` CI pipeline is verified green on:

```text
Python 3.11
Python 3.12
Deterministic integration
Hardened Docker smoke
```

---

# 18. Repository Governance

The repository includes:

- protected `main` branch;
- required pull requests before merge;
- required CI status checks;
- branch-up-to-date requirement;
- force-push protection;
- deletion protection;
- `CODEOWNERS`;
- PR template;
- issue templates;
- `SECURITY.md`;
- Dependabot updates for:
  - Python,
  - GitHub Actions,
  - Docker.

Development should therefore use feature branches:

```bash
git checkout main
git pull
git checkout -b feature/<name>
```

Changes are then pushed and merged through a pull request after required checks pass.

---

# 19. Release Engineering

The repository contains:

```text
.github/workflows/release.yml
```

A published GitHub Release triggers a container build designed to publish to:

```text
ghcr.io/shivam040/agentic-incident-commander
```

The release workflow includes:

- GitHub Container Registry authentication;
- semantic-version image tags;
- SHA image tags;
- `latest` on published releases;
- GitHub Actions build cache;
- OCI metadata;
- build provenance;
- SBOM generation.

The workflow uses the repository-scoped:

```text
GITHUB_TOKEN
```

with:

```text
contents: read
packages: write
```

### Release verification status

The release pipeline is configured, but the repository should only describe GHCR delivery as **fully verified** after at least one published release successfully builds and pushes an image.

---

# 20. Security & Safety Design

This project applies several layers of defense.

## Application-level controls

- structured action schema;
- bounded remediation action types;
- explicit HITL approval;
- rejection enforcement;
- `no_action` routing;
- trusted executor boundary;
- remediation simulation only.

## LLM boundary

The side-effecting remediation capability is **not directly exposed to the LLM**.

## Runtime controls

- non-root container;
- read-only root filesystem;
- dropped capabilities;
- no-new-privileges;
- secret-free deterministic CI.

## Repository controls

- protected `main`;
- required status checks;
- Dependabot;
- security policy;
- review-based merge workflow.

---

# 21. Known Limitations

This project intentionally does **not** claim:

- Kubernetes or AKS integration;
- real cluster/service remediation;
- distributed database/checkpoint persistence;
- multi-region production deployment;
- production SLO improvements;
- enterprise authentication/authorization;
- full secrets-management integration;
- production incident paging;
- autonomous remediation without human approval.

SQLite is suitable for the current single-instance portfolio architecture but is not intended as a distributed production persistence layer.

The remediation tool is simulation-only.

---

# 22. Future Engineering Roadmap

Useful next steps include:

### Platform

- PostgreSQL-backed durable state;
- Redis or event-bus integration;
- distributed worker model;
- production authentication and authorization;
- secrets-manager integration.

### Agent quality

- confidence calibration;
- larger golden evaluation set;
- adversarial and prompt-injection evaluation;
- tool-failure and timeout simulation;
- multi-turn incident memory evaluation;
- automated regression comparison across model versions.

### RAG

- hybrid lexical + vector scoring;
- reranking;
- retrieval attribution;
- larger runbook corpus;
- versioned runbook indexes.

### SRE integration

- OpenTelemetry;
- Prometheus/Grafana dashboards;
- real alert ingestion;
- sandbox Kubernetes integration;
- policy engine before remediation;
- rollback workflows.

### Deployment

- verify first GHCR release;
- image vulnerability scanning;
- dependency/security scanning in CI;
- signed container artifacts;
- staging environment;
- Kubernetes deployment only after safety controls are expanded.

---

# 23. Demo Flow

A simple demonstration sequence is:

```text
1. Start Ollama.
2. Start the API.
3. Create an incident through /docs.
4. Observe telemetry tool calls.
5. Inspect structured RCA.
6. Inspect retrieved runbook evidence.
7. Observe the proposed remediation.
8. Show that execution pauses for approval.
9. Reject the action and demonstrate no execution.
10. Create another incident.
11. Approve the action.
12. Show simulated remediation execution.
13. Query incident history.
14. Inspect /metrics.
15. Show structured logs.
16. Restart the application/container and demonstrate checkpoint recovery.
17. Show the GitHub Actions pipeline and golden evaluation results.
```

This demonstrates the complete system rather than only the LLM response.

---

# 24. What This Project Demonstrates

The project combines AI engineering, backend engineering, SRE concepts, and software-delivery practices:

```text
Agentic AI
+ LangGraph orchestration
+ MCP tool calling
+ structured LLM outputs
+ semantic RAG
+ HITL governance
+ persistent state
+ API engineering
+ observability
+ automated evaluation
+ deterministic testing
+ Docker hardening
+ CI/CD
+ repository governance
```

It is intentionally designed as an **engineering system**, not as a prompt-only chatbot.

---

# 25. Resume-Safe Project Summary

A defensible description of the current project is:

> Engineered a LangGraph-based multi-agent incident-response platform with MCP telemetry/tool integration, structured RCA and remediation planning, semantic runbook RAG, durable HITL checkpoints, Prometheus observability, hardened Docker deployment, and automated Python 3.11/3.12 CI.

A defensible evaluation claim is:

> Evaluated 30 golden incidents across 29 services and five failure classes, achieving 93.3% remediation-action accuracy, 90% RCA case-pass rate, 100% Top-2 runbook retrieval, and zero unsafe executions.

A defensible testing claim is:

> Built deterministic regression and HITL integration testing with a 70% branch-coverage CI gate; the CI-style quality suite currently measures 77.83% branch-aware coverage, with 95% coverage of semantic runbook retrieval logic.

Do not claim real production remediation, Kubernetes deployment, or GHCR delivery until those capabilities are implemented and independently verified.

---

# 26. Additional Documentation

Detailed design notes are available in:

- [`docs/AGENT_WORKFLOW.md`](docs/AGENT_WORKFLOW.md)
- [`docs/PERSISTENCE_AND_RAG.md`](docs/PERSISTENCE_AND_RAG.md)
- [`docs/OBSERVABILITY_AND_OPERATIONS.md`](docs/OBSERVABILITY_AND_OPERATIONS.md)
- [`docs/CONTAINER_DEPLOYMENT.md`](docs/CONTAINER_DEPLOYMENT.md)
- [`docs/CI_CD.md`](docs/CI_CD.md)
- [`SECURITY.md`](SECURITY.md)

---

## Disclaimer

This repository is an educational and portfolio project.

Operational telemetry is fixture/simulation based and remediation is intentionally simulated. Do not connect the remediation path to real production infrastructure without adding appropriate authentication, authorization, policy enforcement, sandboxing, audit controls, rollback mechanisms, and operational review.
