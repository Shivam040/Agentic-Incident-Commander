from incident_commander.state import IncidentState


def remediation_agent(state: IncidentState) -> dict:
    metrics = state.get("metrics", {})
    logs = state.get("logs", [])

    cpu = metrics.get("cpu_percent")
    db_signal = any(
        "connection pool" in line.lower() or "database" in line.lower()
        for line in logs
    )

    if isinstance(cpu, (int, float)) and cpu >= 90 and not db_signal:
        action = "scale_out"
        reason = "CPU saturation is high and no strong database failure signal was found."
        risk = "medium"
    elif db_signal:
        action = "restart_service"
        reason = (
            "Application instances show database/connection-pool pressure; "
            "a simulated rolling restart is proposed."
        )
        risk = "medium"
    else:
        action = "no_action"
        reason = "Evidence is insufficient for an automated state-changing action."
        risk = "low"

    return {
        "remediation_plan": {
            "action": action,
            "reason": reason,
            "risk": risk,
            "requires_human_approval": action != "no_action",
        },
        "status": "remediation_proposed",
    }

