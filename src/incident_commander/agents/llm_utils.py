from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent

from incident_commander.llm import get_chat_model
from incident_commander.observability import observe_agent, record_tool_trace


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False, default=str)
    except TypeError:
        return str(content)


def extract_tool_trace(messages) -> list[dict]:
    trace: list[dict] = []
    for message in messages:
        for call in (getattr(message, "tool_calls", None) or []):
            trace.append(
                {
                    "phase": "request",
                    "name": call.get("name"),
                    "args": call.get("args", {}),
                    "id": call.get("id"),
                }
            )
        if getattr(message, "type", "") == "tool":
            trace.append(
                {
                    "phase": "result",
                    "name": getattr(message, "name", None),
                    "tool_call_id": getattr(message, "tool_call_id", None),
                    "content": _content_to_text(getattr(message, "content", "")),
                }
            )
    return trace


def final_agent_text(messages) -> str:
    if not messages:
        return ""
    return _content_to_text(getattr(messages[-1], "content", ""))


async def run_tool_calling_agent(
    *,
    system_prompt: str,
    user_prompt: str,
    tools,
    name: str,
):
    agent = create_agent(
        model=get_chat_model(),
        tools=tools,
        system_prompt=system_prompt,
        name=name,
    )

    with observe_agent(name):
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_prompt}]}
        )

    messages = result.get("messages", [])
    trace = extract_tool_trace(messages)
    record_tool_trace(trace)
    return final_agent_text(messages), trace

