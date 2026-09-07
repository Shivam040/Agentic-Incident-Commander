from __future__ import annotations

from fastmcp import FastMCP

from incident_commander.tools.remediation import execute_remediation
from incident_commander.tools.runbooks import search_runbooks
from incident_commander.tools.telemetry import get_recent_logs, get_service_metrics

mcp = FastMCP("Incident Commander Tools")


@mcp.tool
def metrics(service: str) -> dict:
    return get_service_metrics(service)


@mcp.tool
def logs(service: str, limit: int = 20) -> list[str]:
    return get_recent_logs(service, limit=limit)


@mcp.tool
def runbook_search(query: str, top_k: int = 3) -> list[dict]:
    """
    Search operational runbooks.

    For incident investigation we always return at least two candidates
    so a single weak lexical match cannot dominate the agent's decision.
    """

    safe_top_k = max(4, min(top_k, 6))

    return search_runbooks(
        query,
        top_k=safe_top_k,
    )


@mcp.tool
def remediate(service: str, action: str, approved: bool = False) -> dict:
    return execute_remediation(service, action, approved)


if __name__ == "__main__":
    mcp.run()

