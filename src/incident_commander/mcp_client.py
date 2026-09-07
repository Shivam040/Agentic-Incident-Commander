from __future__ import annotations

import time
from typing import Iterable

from langchain.mcp import MCPAdapter
from langsmith import traceable

from incident_commander.mcp_server import mcp
from incident_commander.observability import (
    MCP_DIRECT_LATENCY,
    MCP_TOOL_REQUESTS,
    log_event,
)


async def load_mcp_tools(allowed_names: Iterable[str] | None = None):
    async with MCPAdapter(mcp) as adapter:
        tools = await adapter.list_tools()
    if allowed_names is None:
        return tools
    allowed = set(allowed_names)
    return [tool for tool in tools if tool.name in allowed]


@traceable(run_type="tool", name="trusted_mcp_tool_invoke")
async def invoke_mcp_tool(name: str, arguments: dict):
    tools = await load_mcp_tools([name])
    if not tools:
        raise RuntimeError(f"MCP tool {name!r} was not discovered.")

    MCP_TOOL_REQUESTS.labels(tool=name).inc()
    started = time.perf_counter()
    try:
        return await tools[0].ainvoke(arguments)
    finally:
        elapsed = time.perf_counter() - started
        MCP_DIRECT_LATENCY.labels(tool=name).observe(elapsed)
        log_event(
            "mcp_direct_call",
            tool=name,
            duration_ms=round(elapsed * 1000, 2),
        )

