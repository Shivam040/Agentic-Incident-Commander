from incident_commander.state import IncidentState
from incident_commander.tools.runbooks import search_runbooks


def runbook_agent(state: IncidentState) -> dict:
    query = " ".join(
        [
            state.get("service", ""),
            state.get("symptom", ""),
            state.get("diagnosis", ""),
        ]
    )
    return {
        "runbook_context": search_runbooks(query, top_k=2),
        "status": "runbook_grounded",
    }

