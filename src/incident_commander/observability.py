from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable

from prometheus_client import Counter, Histogram

LOGGER_NAME = "incident_commander"

HTTP_REQUESTS = Counter(
    "incident_commander_http_requests_total",
    "HTTP requests handled by the API.",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "incident_commander_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "route"],
)
WORKFLOW_RUNS = Counter(
    "incident_commander_workflow_runs_total",
    "Incident workflow invocations.",
    ["operation", "outcome"],
)
WORKFLOW_LATENCY = Histogram(
    "incident_commander_workflow_duration_seconds",
    "End-to-end LangGraph workflow invocation latency in seconds.",
    ["operation"],
)
AGENT_RUNS = Counter(
    "incident_commander_agent_runs_total",
    "LLM tool-calling agent executions.",
    ["agent", "status"],
)
AGENT_LATENCY = Histogram(
    "incident_commander_agent_duration_seconds",
    "LLM tool-calling agent latency in seconds.",
    ["agent"],
)
MCP_TOOL_REQUESTS = Counter(
    "incident_commander_mcp_tool_requests_total",
    "MCP tool requests emitted by agents or the trusted executor.",
    ["tool"],
)
MCP_TOOL_RESULTS = Counter(
    "incident_commander_mcp_tool_results_total",
    "MCP tool results observed by agents.",
    ["tool"],
)
MCP_DIRECT_LATENCY = Histogram(
    "incident_commander_mcp_direct_duration_seconds",
    "Latency for trusted direct MCP tool invocations in seconds.",
    ["tool"],
)
RAG_RETRIEVALS = Counter(
    "incident_commander_rag_retrievals_total",
    "Runbook retrieval requests by retrieval mode.",
    ["mode"],
)
RAG_LATENCY = Histogram(
    "incident_commander_rag_retrieval_duration_seconds",
    "Runbook retrieval latency in seconds.",
    ["mode"],
)
HITL_DECISIONS = Counter(
    "incident_commander_hitl_decisions_total",
    "Human remediation decisions.",
    ["decision"],
)
REMEDIATION_RESULTS = Counter(
    "incident_commander_remediation_results_total",
    "Remediation outcomes.",
    ["action", "result"],
)
SAFETY_BLOCKS = Counter(
    "incident_commander_safety_blocks_total",
    "State-changing remediation attempts blocked by safety controls.",
    ["reason"],
)


def _log_level() -> int:
    value = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, value, logging.INFO)


def setup_logging() -> None:
    """Configure one JSON-lines logger without replacing Uvicorn's loggers."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_log_level())
    logger.propagate = False

    if logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def log_event(event: str, *, level: int = logging.INFO, **fields) -> None:
    setup_logging()
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level),
        "event": event,
        **fields,
    }
    logging.getLogger(LOGGER_NAME).log(
        level,
        json.dumps(payload, ensure_ascii=False, default=str),
    )


def record_http(method: str, route: str, status: int, elapsed: float) -> None:
    HTTP_REQUESTS.labels(method=method, route=route, status=str(status)).inc()
    HTTP_LATENCY.labels(method=method, route=route).observe(elapsed)


def record_workflow(operation: str, outcome: str, elapsed: float) -> None:
    WORKFLOW_RUNS.labels(operation=operation, outcome=outcome).inc()
    WORKFLOW_LATENCY.labels(operation=operation).observe(elapsed)


def record_tool_trace(trace: Iterable[dict]) -> None:
    for item in trace:
        tool = str(item.get("name") or "unknown")
        if item.get("phase") == "request":
            MCP_TOOL_REQUESTS.labels(tool=tool).inc()
        elif item.get("phase") == "result":
            MCP_TOOL_RESULTS.labels(tool=tool).inc()


def record_hitl_decision(approved: bool) -> None:
    HITL_DECISIONS.labels(decision="approved" if approved else "rejected").inc()


def record_remediation(action: str, executed: bool) -> None:
    REMEDIATION_RESULTS.labels(
        action=action or "unknown",
        result="executed" if executed else "skipped",
    ).inc()


def record_safety_block(reason: str) -> None:
    SAFETY_BLOCKS.labels(reason=reason).inc()


@contextmanager
def observe_agent(agent: str):
    started = time.perf_counter()
    try:
        yield
    except Exception:
        AGENT_RUNS.labels(agent=agent, status="error").inc()
        raise
    else:
        AGENT_RUNS.labels(agent=agent, status="success").inc()
    finally:
        AGENT_LATENCY.labels(agent=agent).observe(time.perf_counter() - started)


@contextmanager
def observe_rag():
    """Return a mutable result dict so callers can report the final mode."""
    started = time.perf_counter()
    result = {"mode": "unknown"}
    try:
        yield result
    finally:
        mode = str(result.get("mode") or "unknown")
        RAG_RETRIEVALS.labels(mode=mode).inc()
        RAG_LATENCY.labels(mode=mode).observe(time.perf_counter() - started)

