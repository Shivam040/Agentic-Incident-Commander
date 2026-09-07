from __future__ import annotations

import json

from incident_commander.config import get_data_root

DATA_ROOT = get_data_root()


def _load(name: str):
    with (DATA_ROOT / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def get_service_metrics(service: str) -> dict:
    metrics = _load("telemetry.json")
    return metrics.get(
        service,
        {
            "service": service,
            "status": "unknown",
            "cpu_percent": None,
            "memory_percent": None,
            "error_rate": None,
            "p95_latency_ms": None,
        },
    )


def get_recent_logs(service: str, limit: int = 20) -> list[str]:
    logs = _load("logs.json")
    return logs.get(service, [])[-limit:]

