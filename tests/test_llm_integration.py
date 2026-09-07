import asyncio
import os
import pytest
from incident_commander.agents.agent_runtime import run_telemetry_agent

@pytest.mark.skipif(os.getenv("RUN_LLM_TESTS", "0") != "1", reason="Set RUN_LLM_TESTS=1 only when Ollama/provider is available.")
def test_llm_telemetry_agent_really_calls_mcp_tools(monkeypatch):
    monkeypatch.setenv("AI_MODE", "llm")
    result = asyncio.run(run_telemetry_agent({"service": "checkout-api", "symptom": "latency and elevated 5xx errors"}))
    assert result["telemetry_tool_call_verified"] is True
    requested = {item["name"] for item in result["telemetry_tool_trace"] if item["phase"] == "request"}
    assert {"metrics", "logs"}.issubset(requested)

