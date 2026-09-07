import asyncio
import json
import os
from incident_commander.agents.agent_runtime import run_rca_agent, run_runbook_agent, run_telemetry_agent

async def main():
    os.environ.setdefault("AI_MODE", "llm")
    state = {"service": "checkout-api", "symptom": "latency and elevated 5xx errors"}
    state.update(await run_telemetry_agent(state))
    state.update(await run_rca_agent(state))
    state.update(await run_runbook_agent(state))
    print(json.dumps({
        "telemetry_tool_call_verified": state.get("telemetry_tool_call_verified"),
        "telemetry_tool_trace": state.get("telemetry_tool_trace"),
        "diagnosis": state.get("diagnosis"),
        "diagnosis_confidence": state.get("diagnosis_confidence"),
        "runbook_tool_call_verified": state.get("runbook_tool_call_verified"),
        "runbook_tool_trace": state.get("runbook_tool_trace"),
    }, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())

