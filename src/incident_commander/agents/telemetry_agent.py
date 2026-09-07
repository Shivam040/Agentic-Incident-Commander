from incident_commander.state import IncidentState
from incident_commander.tools.telemetry import get_recent_logs, get_service_metrics


def telemetry_agent(state: IncidentState) -> dict:
    service = state["service"]
    return {
        "metrics": get_service_metrics(service),
        "logs": get_recent_logs(service),
        "status": "telemetry_collected",
    }

