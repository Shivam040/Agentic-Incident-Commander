from incident_commander.state import IncidentState

def report_agent(state: IncidentState) -> dict:
    plan = state.get("remediation_plan", {})
    execution = state.get("execution_result", {})
    report = (
        f"Incident report for {state.get('service')}.\n"
        f"Symptom: {state.get('symptom')}.\n"
        f"AI mode/provider/model: {state.get('ai_mode')}/{state.get('ai_provider')}/{state.get('model_name')}.\n"
        f"Telemetry MCP calls verified: {state.get('telemetry_tool_call_verified', False)}.\n"
        f"Runbook MCP call verified: {state.get('runbook_tool_call_verified', False)}.\n"
        f"Diagnosis: {state.get('diagnosis')} (confidence={state.get('diagnosis_confidence')}).\n"
        f"Evidence: {state.get('diagnosis_evidence', [])}.\n"
        f"Proposed action: {plan.get('action')} (risk={plan.get('risk')}).\n"
        f"Human decision: {state.get('approval', {})}.\n"
        f"Execution: {execution}."
    )
    return {"report": report, "status": "completed"}

