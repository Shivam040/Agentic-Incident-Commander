from __future__ import annotations
from typing import TypedDict

class IncidentState(TypedDict, total=False):
    thread_id: str
    service: str
    symptom: str
    telemetry_summary: str
    telemetry_tool_trace: list[dict]
    telemetry_tool_call_verified: bool
    diagnosis: str
    diagnosis_confidence: float
    diagnosis_evidence: list[str]
    diagnosis_conflicting_evidence: list[str]
    next_checks: list[str]
    runbook_summary: str
    runbook_tool_trace: list[dict]
    runbook_tool_call_verified: bool
    remediation_plan: dict
    approval: dict
    execution_result: dict
    ai_mode: str
    ai_provider: str
    model_name: str
    status: str
    report: str

