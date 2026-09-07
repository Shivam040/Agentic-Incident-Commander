from __future__ import annotations

from datetime import datetime, timezone

from incident_commander.observability import (
    log_event,
    record_remediation,
    record_safety_block,
)

ALLOWED_DEMO_ACTIONS = {"restart_service", "scale_out", "no_action"}


def execute_remediation(service: str, action: str, approved: bool) -> dict:
    if not approved:
        record_safety_block("missing_human_approval")
        record_remediation(action, False)
        log_event(
            "remediation_blocked",
            service=service,
            action=action,
            reason="missing_human_approval",
        )
        return {
            "executed": False,
            "service": service,
            "action": action,
            "reason": "Human approval not granted.",
        }

    if action not in ALLOWED_DEMO_ACTIONS:
        record_safety_block("action_not_allowlisted")
        record_remediation(action, False)
        log_event(
            "remediation_blocked",
            service=service,
            action=action,
            reason="action_not_allowlisted",
        )
        return {
            "executed": False,
            "service": service,
            "action": action,
            "reason": "Action not allow-listed.",
        }

    record_remediation(action, True)
    log_event(
        "remediation_executed",
        service=service,
        action=action,
        mode="simulation",
    )
    return {
        "executed": True,
        "mode": "simulation",
        "service": service,
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Simulated remediation '{action}' for '{service}'.",
    }

