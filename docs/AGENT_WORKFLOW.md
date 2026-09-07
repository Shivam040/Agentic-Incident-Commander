# Stage 2 — Real LLM tool calling

## What changed from v0.1

v0.1 had a real LangGraph workflow and HITL boundary, but specialist decisions were deterministic.

v0.2 adds:

1. **LangChain agents**
   - Telemetry Agent invokes MCP metrics/log tools.
   - Runbook Agent invokes MCP runbook search.
2. **Current LangChain MCP integration**
   - FastMCP is the server.
   - `langchain.mcp.MCPAdapter` discovers/adapts FastMCP tools.
   - Development uses an in-process FastMCP server.
3. **Structured LLM reasoning**
   - RCA returns validated `RCAAssessment`.
   - Remediation planning returns validated `RemediationProposal`.
4. **HITL outside the model**
   - LLM proposes; trusted graph code governs.
   - Reject/no-action routes around the side-effecting tool entirely.
   - Only approval reaches MCP `remediate`.

## Trust boundary

```text
LLM CAN:
  call scoped read-only metrics/log/runbook tools
  propose RCA
  propose allow-listed remediation

LLM CANNOT:
  bypass the approval node
  invoke the remediation MCP tool from its planning loop
  invent a new remediation action outside the schema
  turn the demo executor into a real production action
```

## Stage 2 proof

Run:

```bash
python scripts/smoke_llm.py
```

Before claiming LLM/MCP tool calling, verify:

```text
telemetry_tool_call_verified = true
runbook_tool_call_verified = true
```
