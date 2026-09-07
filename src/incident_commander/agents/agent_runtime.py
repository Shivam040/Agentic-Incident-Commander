from __future__ import annotations
import json
from incident_commander.agents.llm_utils import run_tool_calling_agent
from incident_commander.config import get_settings
from incident_commander.llm import get_chat_model
from incident_commander.mcp_client import load_mcp_tools
from incident_commander.prompts import RCA_PROMPT, REMEDIATION_PROMPT, RUNBOOK_AGENT_PROMPT, TELEMETRY_AGENT_PROMPT
from incident_commander.schemas import RCAAssessment, RemediationProposal
from incident_commander.state import IncidentState
from incident_commander.agents.rca_agent import rca_agent as deterministic_rca
from incident_commander.agents.remediation_agent import remediation_agent as deterministic_remediation
from incident_commander.agents.runbook_agent import runbook_agent as deterministic_runbook
from incident_commander.agents.telemetry_agent import telemetry_agent as deterministic_telemetry

def _model_metadata() -> dict:
    s = get_settings()
    model = s.ollama_model if s.ai_provider == "ollama" else s.openai_model
    return {"ai_mode": s.ai_mode, "ai_provider": s.ai_provider, "model_name": model}

async def run_telemetry_agent(state: IncidentState) -> dict:
    settings = get_settings()
    if not settings.llm_enabled:
        result = deterministic_telemetry(state)
        return {
            "telemetry_summary": f"Metrics: {json.dumps(result['metrics'], default=str)}\nLogs: {json.dumps(result['logs'], default=str)}",
            "telemetry_tool_trace": [],
            "telemetry_tool_call_verified": False,
            "status": "telemetry_collected_deterministic",
            **_model_metadata(),
        }
    tools = await load_mcp_tools(["metrics", "logs"])
    summary, trace = await run_tool_calling_agent(
        system_prompt=TELEMETRY_AGENT_PROMPT,
        user_prompt=f"Investigate service={state['service']!r}. Reported symptom={state['symptom']!r}. Call the telemetry tools and summarize evidence.",
        tools=tools,
        name="telemetry_agent",
    )
    called = {x.get("name") for x in trace if x.get("phase") == "request"}
    return {
        "telemetry_summary": summary,
        "telemetry_tool_trace": trace,
        "telemetry_tool_call_verified": {"metrics", "logs"}.issubset(called),
        "status": "telemetry_collected_llm",
        **_model_metadata(),
    }

async def run_rca_agent(state: IncidentState) -> dict:
    settings = get_settings()
    if not settings.llm_enabled:
        legacy = deterministic_telemetry(state)
        result = deterministic_rca(legacy)
        return {
            "diagnosis": result["diagnosis"],
            "diagnosis_confidence": result["diagnosis_confidence"],
            "diagnosis_evidence": [],
            "diagnosis_conflicting_evidence": [],
            "next_checks": [],
            "status": "rca_complete_deterministic",
            **_model_metadata(),
        }
    structured = get_chat_model().with_structured_output(RCAAssessment)
    assessment = await structured.ainvoke([
        ("system", RCA_PROMPT),
        ("human", f"Service: {state['service']}\nSymptom: {state['symptom']}\n\nTelemetry Agent evidence:\n{state.get('telemetry_summary','')}")
    ])
    return {
        "diagnosis": assessment.root_cause,
        "diagnosis_confidence": assessment.confidence,
        "diagnosis_evidence": assessment.evidence,
        "diagnosis_conflicting_evidence": assessment.conflicting_evidence,
        "next_checks": assessment.next_checks,
        "status": "rca_complete_llm",
        **_model_metadata(),
    }

async def run_runbook_agent(state: IncidentState) -> dict:
    settings = get_settings()
    if not settings.llm_enabled:
        legacy = deterministic_telemetry(state)
        legacy.update({
            "service": state["service"],
            "symptom": state["symptom"],
            "diagnosis": state.get("diagnosis", ""),
        })
        result = deterministic_runbook(legacy)
        return {
            "runbook_summary": json.dumps(result["runbook_context"], ensure_ascii=False, default=str),
            "runbook_tool_trace": [],
            "runbook_tool_call_verified": False,
            "status": "runbook_grounded_deterministic",
            **_model_metadata(),
        }
    tools = await load_mcp_tools(["runbook_search"])
    summary, trace = await run_tool_calling_agent(
        system_prompt=RUNBOOK_AGENT_PROMPT,
        user_prompt=(
            f"Service: {state['service']}\nSymptom: {state['symptom']}\n"
            f"Telemetry evidence:\n{state.get('telemetry_summary','')}\n\n"
            f"RCA: {state.get('diagnosis','')}\nConfidence: {state.get('diagnosis_confidence',0.0)}\n"
            "Search the runbooks and return grounded operational guidance."
        ),
        tools=tools,
        name="runbook_agent",
    )
    called = {x.get("name") for x in trace if x.get("phase") == "request"}
    return {
        "runbook_summary": summary,
        "runbook_tool_trace": trace,
        "runbook_tool_call_verified": "runbook_search" in called,
        "status": "runbook_grounded_llm",
        **_model_metadata(),
    }

async def run_remediation_agent(state: IncidentState) -> dict:
    settings = get_settings()
    if not settings.llm_enabled:
        legacy = deterministic_telemetry(state)
        result = deterministic_remediation(legacy)
        return {
            "remediation_plan": {**result["remediation_plan"], "expected_impact": "Deterministic demo decision."},
            "status": "remediation_proposed_deterministic",
            **_model_metadata(),
        }
    structured = get_chat_model().with_structured_output(RemediationProposal)
    proposal = await structured.ainvoke([
        ("system", REMEDIATION_PROMPT),
        ("human", (
            f"Service: {state['service']}\nSymptom: {state['symptom']}\n\n"
            f"Telemetry evidence:\n{state.get('telemetry_summary','')}\n\n"
            f"RCA: {state.get('diagnosis','')}\nConfidence: {state.get('diagnosis_confidence',0.0)}\n"
            f"Evidence: {state.get('diagnosis_evidence',[])}\n\n"
            f"Retrieved runbook guidance:\n{state.get('runbook_summary','')}"
        ))
    ])
    requires_approval = proposal.action != "no_action"
    return {
        "remediation_plan": {
            "action": proposal.action,
            "reason": proposal.reason,
            "risk": proposal.risk,
            "expected_impact": proposal.expected_impact,
            "requires_human_approval": requires_approval,
        },
        "status": "remediation_proposed_llm",
        **_model_metadata(),
    }


