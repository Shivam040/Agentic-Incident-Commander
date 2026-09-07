from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from incident_commander.graph import build_graph


async def main() -> None:
    # Keep this test free and deterministic; no LLM is required.
    os.environ["AI_MODE"] = "deterministic"
    os.environ["RUNBOOK_RETRIEVAL"] = "lexical"

    thread_id = f"persistence-smoke-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "checkpoints.sqlite")

        # First process/lifecycle: create an interrupted incident.
        async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
            graph = build_graph(saver)
            await graph.ainvoke(
                {
                    "thread_id": thread_id,
                    "service": "recommendation-api",
                    "symptom": "high latency and elevated 503 errors during traffic spike",
                    "status": "new",
                },
                config=config,
            )
            before_restart = await graph.aget_state(config)
            assert before_restart.values
            assert "approval_gate" in before_restart.next

        # Simulated server restart: close DB connection, then reopen a new saver.
        async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
            graph = build_graph(saver)
            after_restart = await graph.aget_state(config)

            assert after_restart.values, "Checkpoint disappeared after restart"
            assert "approval_gate" in after_restart.next

            # Resume the exact same thread after the simulated restart.
            result = await graph.ainvoke(
                Command(
                    resume={
                        "approved": False,
                        "feedback": "Persistence smoke-test rejection",
                    }
                ),
                config=config,
            )

            assert result["approval"]["approved"] is False
            assert result["execution_result"]["executed"] is False
            assert result["status"] == "completed"

    print("Stage 3A persistence smoke test: PASS")
    print(f"Thread survived saver close/reopen: {thread_id}")


if __name__ == "__main__":
    asyncio.run(main())

