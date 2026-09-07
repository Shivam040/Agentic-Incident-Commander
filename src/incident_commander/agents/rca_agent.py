from incident_commander.state import IncidentState


def rca_agent(state: IncidentState) -> dict:
    metrics = state.get("metrics", {})
    logs = state.get("logs", [])

    error_rate = metrics.get("error_rate")
    p95 = metrics.get("p95_latency_ms")
    cpu = metrics.get("cpu_percent")

    hypotheses: list[str] = []
    confidence = 0.35

    if isinstance(error_rate, (int, float)) and error_rate >= 0.10:
        hypotheses.append("elevated application error rate")
        confidence += 0.20

    if isinstance(p95, (int, float)) and p95 >= 1000:
        hypotheses.append("severe request latency")
        confidence += 0.15

    if isinstance(cpu, (int, float)) and cpu >= 85:
        hypotheses.append("CPU saturation")
        confidence += 0.15

    db_signal = any(
        "database" in line.lower()
        or "connection pool" in line.lower()
        or "timeout" in line.lower()
        for line in logs
    )
    if db_signal:
        hypotheses.append("database/connection-pool pressure")
        confidence += 0.10

    confidence = min(confidence, 0.95)

    if hypotheses:
        diagnosis = (
            "Likely incident involving "
            + ", ".join(hypotheses)
            + ". Evidence should be validated against the runbook before remediation."
        )
    else:
        diagnosis = "No high-confidence failure signature found. Continue diagnostics."

    return {
        "diagnosis": diagnosis,
        "diagnosis_confidence": round(confidence, 2),
        "status": "rca_complete",
    }

