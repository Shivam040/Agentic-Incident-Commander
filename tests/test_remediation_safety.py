import asyncio
from incident_commander.agents.agent_runtime import run_remediation_agent
from incident_commander.tools.remediation import execute_remediation

def test_side_effect_tool_still_refuses_without_approval():
    result = execute_remediation("checkout-api", "restart_service", False)
    assert result["executed"] is False

def test_deterministic_fallback_keeps_approval_requirement(monkeypatch):
    monkeypatch.setenv("AI_MODE", "deterministic")
    result = asyncio.run(run_remediation_agent({"service": "checkout-api", "symptom": "latency and 5xx spike"}))
    plan = result["remediation_plan"]
    if plan["action"] != "no_action":
        assert plan["requires_human_approval"] is True

