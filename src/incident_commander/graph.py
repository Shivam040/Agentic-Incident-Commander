from __future__ import annotations

import json

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from incident_commander.agents.report_agent import report_agent
from incident_commander.agents.agent_runtime import (
    run_rca_agent,
    run_remediation_agent,
    run_runbook_agent,
    run_telemetry_agent,
)
from incident_commander.mcp_client import invoke_mcp_tool
from incident_commander.observability import (
    log_event,
    record_hitl_decision,
    record_remediation,
    record_safety_block,
)
from incident_commander.state import IncidentState


def supervisor(state: IncidentState) -> dict:
    """Accept the incident and start the specialist-agent workflow."""
    log_event(
        "incident_accepted",
        thread_id=state.get("thread_id"),
        service=state.get("service"),
    )
    return {"status": "supervisor_accepted"}


def normalize_mcp_result(result):
    """Normalize MCP/LangChain content blocks into plain Python data."""
    if hasattr(result, "model_dump"):
        result = result.model_dump()

    if isinstance(result, list) and result:
        first = result[0]

        if hasattr(first, "model_dump"):
            first = first.model_dump()

        if isinstance(first, dict):
            text = first.get("text")
            if isinstance(text, str):
                try:
                    decoded = json.loads(text)
                    if isinstance(decoded, dict):
                        return decoded
                    return {"data": decoded}
                except json.JSONDecodeError:
                    return {"raw": text}

        return {"raw": result}

    if isinstance(result, dict):
        return result

    return {"raw": str(result)}


def approval_gate(state: IncidentState) -> dict:
    plan = state.get("remediation_plan", {})
    action = plan.get("action", "no_action")

    if action == "no_action":
        record_remediation("no_action", False)
        log_event(
            "remediation_not_required",
            thread_id=state.get("thread_id"),
            service=state.get("service"),
        )
        return {
            "approval": {
                "approved": False,
                "feedback": "No state-changing action proposed.",
                "automatic": True,
            },
            "execution_result": {
                "executed": False,
                "action": "no_action",
                "reason": "No state-changing remediation was proposed.",
            },
            "status": "no_action_required",
        }

    log_event(
        "hitl_approval_required",
        thread_id=state.get("thread_id"),
        service=state.get("service"),
        action=action,
    )
    decision = interrupt(
        {
            "type": "remediation_approval",
            "service": state.get("service"),
            "plan": plan,
            "rca": {
                "diagnosis": state.get("diagnosis"),
                "confidence": state.get("diagnosis_confidence"),
                "evidence": state.get("diagnosis_evidence", []),
            },
            "message": "Approve or reject the proposed remediation.",
        }
    )

    approved = bool(decision.get("approved", False))
    feedback = str(decision.get("feedback", ""))
    record_hitl_decision(approved)
    log_event(
        "hitl_decision",
        thread_id=state.get("thread_id"),
        service=state.get("service"),
        action=action,
        approved=approved,
    )

    updates = {
        "approval": {
            "approved": approved,
            "feedback": feedback,
            "automatic": False,
        },
        "status": "approved" if approved else "rejected",
    }

    if not approved:
        record_remediation(action, False)
        updates["execution_result"] = {
            "executed": False,
            "service": state.get("service"),
            "action": action,
            "reason": "Human rejected the proposed remediation.",
            "feedback": feedback,
        }

    return updates


def route_after_approval(state: IncidentState) -> str:
    plan = state.get("remediation_plan", {})
    approval = state.get("approval", {})

    action = plan.get("action", "no_action")
    approved = bool(approval.get("approved", False))

    if action != "no_action" and approved:
        return "execute"
    return "report"


async def remediation_executor(state: IncidentState) -> dict:
    plan = state.get("remediation_plan", {})
    approval = state.get("approval", {})

    approved = bool(approval.get("approved", False))
    action = plan.get("action", "no_action")

    if not approved:
        record_safety_block("executor_missing_approval")
        record_remediation(action, False)
        log_event(
            "executor_safety_block",
            thread_id=state.get("thread_id"),
            service=state.get("service"),
            action=action,
        )
        return {
            "execution_result": {
                "executed": False,
                "service": state.get("service"),
                "action": action,
                "reason": "Execution blocked because human approval is absent.",
            },
            "status": "remediation_skipped",
        }

    result = await invoke_mcp_tool(
        "remediate",
        {
            "service": state["service"],
            "action": action,
            "approved": True,
        },
    )

    result = normalize_mcp_result(result)
    executed = bool(result.get("executed", False))
    log_event(
        "executor_complete",
        thread_id=state.get("thread_id"),
        service=state.get("service"),
        action=action,
        executed=executed,
    )

    return {
        "execution_result": result,
        "status": "remediation_executed" if executed else "remediation_skipped",
    }


def build_graph(checkpointer):
    """Build the workflow with an injected durable checkpointer."""
    builder = StateGraph(IncidentState)

    builder.add_node("supervisor", supervisor)
    builder.add_node("telemetry_agent", run_telemetry_agent)
    builder.add_node("rca_agent", run_rca_agent)
    builder.add_node("runbook_agent", run_runbook_agent)
    builder.add_node("remediation_agent", run_remediation_agent)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("remediation_executor", remediation_executor)
    builder.add_node("report_agent", report_agent)

    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", "telemetry_agent")
    builder.add_edge("telemetry_agent", "rca_agent")
    builder.add_edge("rca_agent", "runbook_agent")
    builder.add_edge("runbook_agent", "remediation_agent")
    builder.add_edge("remediation_agent", "approval_gate")

    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {
            "execute": "remediation_executor",
            "report": "report_agent",
        },
    )

    builder.add_edge("remediation_executor", "report_agent")
    builder.add_edge("report_agent", END)

    return builder.compile(checkpointer=checkpointer)

