# Stage 3 — Durable state, semantic vector RAG, and evaluation

Stage 2 proved real LLM tool calling, MCP, structured RCA, remediation planning,
and human-in-the-loop execution. Stage 3 focuses on **reliability and evaluation**.

## 3A — Durable LangGraph checkpoints

### Previous limitation

Stage 2 compiled the graph with `InMemorySaver()`. An interrupted HITL thread was
lost whenever Uvicorn reloaded or the Python process restarted.

### Stage 3 design

FastAPI now owns an `AsyncSqliteSaver` for the entire application lifespan:

```text
FastAPI starts
    |
    v
open SQLite checkpointer
    |
    v
compile LangGraph(checkpointer=AsyncSqliteSaver)
    |
    v
serve incidents / HITL decisions
    |
    v
FastAPI shuts down
    |
    v
close SQLite connection
```

The compiled graph is stored on `app.state.graph` rather than as a module-level
singleton. Async endpoints use `ainvoke()` and `aget_state()`.

Default checkpoint file:

```text
data/checkpoints/incident_commander.sqlite
```

This lets an interrupted incident survive a server restart and resume using the
same `thread_id`.

## 3B — Semantic vector RAG

### Previous limitation

Stage 2 ranked entire runbooks using token overlap. That caused retrieval
nondeterminism and could allow a weak lexical match to dominate.

### Stage 3 design

```text
Markdown runbooks
      |
      v
heading-aware chunks
      |
      v
Ollama embeddings (nomic-embed-text)
      |
      v
persistent JSON vector index
      |
      v
query embedding
      |
      v
cosine similarity
      |
      v
top-k runbook chunks
      |
      v
Runbook Agent
```

Default index:

```text
data/vector_index/runbooks.json
```

The index contains transparent metadata and dense vectors. It automatically
rebuilds when runbook contents change or the configured embedding model changes.

If Ollama/the embedding model is unavailable, retrieval explicitly returns
`retrieval_mode = lexical_fallback`; it does **not** silently pretend semantic
vector retrieval succeeded.

## 3C — Evaluation harness

`evaluations/incident_cases.json` is a golden set. `scripts/evaluate_agent.py`
runs each incident without approving state-changing actions and reports:

- telemetry MCP tool-call rate
- runbook MCP tool-call rate
- RCA keyword match rate
- action accuracy
- HITL gate accuracy
- runbook hit rate
- semantic-vector usage rate
- safety compliance rate

Detailed results are saved to:

```text
evaluations/latest_results.json
```

## Safety invariants retained from Stage 2

- The LLM does not receive the remediation tool during planning.
- State-changing actions require LangGraph HITL approval.
- Rejected actions route directly to reporting.
- The executor independently checks approval as defense in depth.
- MCP remediation remains simulation-only.
