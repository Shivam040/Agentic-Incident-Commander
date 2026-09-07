from __future__ import annotations

import os
from pathlib import Path

os.environ["AI_MODE"] = "deterministic"
os.environ["RUNBOOK_RETRIEVAL"] = "lexical"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["CHECKPOINT_DB_PATH"] = "data/checkpoints/observability_smoke.sqlite"

from fastapi.testclient import TestClient

from incident_commander.api import app
from incident_commander.config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "data" / "checkpoints" / "observability_smoke.sqlite"


def main() -> None:
    for candidate in [DB_PATH, Path(f"{DB_PATH}-shm"), Path(f"{DB_PATH}-wal")]:
        if candidate.exists():
            candidate.unlink()

    with TestClient(app) as client:
        response = client.post(
            "/incidents",
            json={
                "service": "checkout-api",
                "symptom": "latency and elevated 503 errors",
            },
        )
        response.raise_for_status()
        assert response.headers.get("X-Request-ID")

        health = client.get("/health")
        health.raise_for_status()
        observability = health.json()["observability"]
        assert observability["prometheus_metrics"] is True
        assert observability["json_logging"] is True

        metrics = client.get("/metrics")
        metrics.raise_for_status()
        body = metrics.text

        required = [
            "incident_commander_http_requests_total",
            "incident_commander_workflow_runs_total",
            "incident_commander_workflow_duration_seconds",
            "incident_commander_rag_retrievals_total",
            "incident_commander_remediation_results_total",
        ]
        missing = [name for name in required if name not in body]
        assert not missing, f"Missing Prometheus metrics: {missing}"

    print("Stage 4A observability smoke test: PASS")
    print("Verified JSON request logging, request IDs, /health, and /metrics.")


if __name__ == "__main__":
    main()

