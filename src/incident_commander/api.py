from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from uuid import uuid4

# Restrict checkpoint deserialization to safer msgpack behavior when supported.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from fastapi import FastAPI, HTTPException, Request, Response
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from incident_commander import __version__
from incident_commander.config import get_settings, resolve_project_path
from incident_commander.graph import build_graph
from incident_commander.observability import (
    log_event,
    record_http,
    record_workflow,
    setup_logging,
)


class IncidentRequest(BaseModel):
    service: str = Field(min_length=1)
    symptom: str = Field(min_length=1)


class DecisionRequest(BaseModel):
    approved: bool
    feedback: str = ""


def _config(
    thread_id: str,
    *,
    service: str | None = None,
    operation: str = "incident",
) -> dict:
    tags = ["incident-commander", operation]
    metadata = {"thread_id": thread_id, "operation": operation}
    if service:
        tags.append(f"service:{service}")
        metadata["service"] = service

    return {
        "configurable": {"thread_id": thread_id},
        "run_name": f"incident-commander:{operation}",
        "tags": tags,
        "metadata": metadata,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    checkpoint_path = resolve_project_path(settings.checkpoint_db_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    log_event(
        "application_start",
        version=__version__,
        checkpoint_backend="sqlite",
        langsmith_tracing=settings.langsmith_tracing,
        langsmith_project=settings.langsmith_project,
    )

    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        app.state.graph = build_graph(checkpointer)
        app.state.checkpoint_path = str(checkpoint_path)
        yield

    log_event("application_stop", version=__version__)


app = FastAPI(
    title="Agentic Incident Commander",
    version=__version__,
    description=(
        "LangGraph + LangChain + MCP + durable HITL checkpoints + semantic "
        "vector RAG + Prometheus observability + optional LangSmith tracing"
    ),
    lifespan=lifespan,
)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started = time.perf_counter()
    status = 500

    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        elapsed = time.perf_counter() - started
        route_object = request.scope.get("route")
        route = getattr(route_object, "path", request.url.path)
        record_http(request.method, route, status, elapsed)
        log_event(
            "http_request",
            request_id=request_id,
            method=request.method,
            route=route,
            status=status,
            duration_ms=round(elapsed * 1000, 2),
        )


def _graph(request: Request):
    return request.app.state.graph


@app.get("/health")
def health(request: Request):
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "ai_mode": settings.ai_mode,
        "ai_provider": settings.ai_provider,
        "model": (
            settings.ollama_model
            if settings.ai_provider == "ollama"
            else settings.openai_model
        ),
        "checkpoint_backend": "sqlite",
        "checkpoint_path": request.app.state.checkpoint_path,
        "runbook_retrieval": settings.runbook_retrieval,
        "embedding_model": settings.ollama_embedding_model,
        "observability": {
            "prometheus_metrics": True,
            "json_logging": True,
            "langsmith_tracing": settings.langsmith_tracing,
            "langsmith_project": settings.langsmith_project,
        },
        "features": [
            "langgraph-orchestration",
            "langchain-agents",
            "mcp-tool-discovery",
            "llm-tool-calling",
            "structured-output",
            "human-in-the-loop",
            "durable-sqlite-checkpoints",
            "semantic-vector-rag",
            "evaluation-harness",
            "prometheus-metrics",
            "structured-json-logging",
            "optional-langsmith-tracing",
            "github-actions-ci",
            "hardened-docker-runtime",
        ],
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/incidents")
async def create_incident(request: Request, payload: IncidentRequest):
    graph = _graph(request)
    thread_id = str(uuid4())
    config = _config(
        thread_id,
        service=payload.service,
        operation="create-incident",
    )
    started = time.perf_counter()

    try:
        result = await graph.ainvoke(
            {
                "thread_id": thread_id,
                "service": payload.service,
                "symptom": payload.symptom,
                "status": "new",
            },
            config=config,
        )
        snapshot = await graph.aget_state(config)
    except Exception:
        record_workflow("create", "error", time.perf_counter() - started)
        raise

    outcome = "awaiting_human" if snapshot.next else "completed"
    record_workflow("create", outcome, time.perf_counter() - started)
    log_event(
        "workflow_create_complete",
        thread_id=thread_id,
        service=payload.service,
        outcome=outcome,
        next=list(snapshot.next),
    )

    return {
        "thread_id": thread_id,
        "state": result,
        "next": list(snapshot.next),
        "interrupts": [
            intr.value
            for task in snapshot.tasks
            for intr in getattr(task, "interrupts", ())
        ],
    }


@app.post("/incidents/{thread_id}/decision")
async def submit_decision(
    thread_id: str,
    decision: DecisionRequest,
    request: Request,
):
    graph = _graph(request)
    base_config = _config(thread_id, operation="read-before-decision")
    snapshot = await graph.aget_state(base_config)

    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Incident thread not found")

    if not snapshot.next:
        raise HTTPException(
            status_code=409,
            detail="Incident is not waiting for a decision",
        )

    service = str(snapshot.values.get("service", ""))
    config = _config(thread_id, service=service, operation="resume-after-decision")
    started = time.perf_counter()

    try:
        result = await graph.ainvoke(
            Command(
                resume={
                    "approved": decision.approved,
                    "feedback": decision.feedback,
                }
            ),
            config=config,
        )
    except Exception:
        record_workflow("decision", "error", time.perf_counter() - started)
        raise

    record_workflow("decision", "completed", time.perf_counter() - started)
    return {"thread_id": thread_id, "state": result}


@app.get("/incidents/{thread_id}")
async def get_incident(thread_id: str, request: Request):
    graph = _graph(request)
    config = _config(thread_id, operation="read-incident")
    snapshot = await graph.aget_state(config)

    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Incident thread not found")

    return {
        "thread_id": thread_id,
        "state": snapshot.values,
        "next": list(snapshot.next),
        "interrupts": [
            intr.value
            for task in snapshot.tasks
            for intr in getattr(task, "interrupts", ())
        ],
    }


@app.get("/incidents/{thread_id}/history")
async def get_incident_history(thread_id: str, request: Request):
    graph = _graph(request)
    config = _config(thread_id, operation="read-history")

    snapshots = []
    async for snapshot in graph.aget_state_history(config):
        snapshots.append(
            {
                "values": snapshot.values,
                "next": list(snapshot.next),
                "metadata": snapshot.metadata,
                "created_at": snapshot.created_at,
            }
        )

    if not snapshots:
        raise HTTPException(status_code=404, detail="Incident thread not found")

    return {
        "thread_id": thread_id,
        "checkpoint_count": len(snapshots),
        "history": snapshots,
    }

