from __future__ import annotations

import asyncio
import json
import math
import os
import statistics
import time
from collections import Counter, defaultdict
from uuid import uuid4

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from incident_commander.config import PROJECT_ROOT
from incident_commander.graph import build_graph

CASES_PATH = PROJECT_ROOT / "evaluations" / "incident_cases.json"
RESULTS_PATH = PROJECT_ROOT / "evaluations" / "latest_results.json"
DB_PATH = PROJECT_ROOT / "evaluations" / "eval_checkpoints.sqlite"


def _keyword_details(text: str, keywords: list[str], minimum_matches: int | None = None) -> tuple[bool, float, list[str]]:
    if not keywords:
        return True, 1.0, []
    lowered = text.lower()
    matched = [keyword for keyword in keywords if keyword.lower() in lowered]
    required = minimum_matches if minimum_matches is not None else max(1, math.ceil(len(keywords) / 2))
    required = min(required, len(keywords))
    return len(matched) >= required, round(len(matched) / len(keywords), 3), matched


def _trace_text(state: dict) -> str:
    return json.dumps(state.get("runbook_tool_trace", []), ensure_ascii=False)


def _retrieved_runbook_paths(state: dict) -> list[str]:
    paths: list[str] = []
    for item in state.get("runbook_tool_trace", []):
        if item.get("phase") != "result" or item.get("name") != "runbook_search":
            continue
        try:
            outer = json.loads(item.get("content", "[]"))
            for block in outer if isinstance(outer, list) else []:
                text = block.get("text") if isinstance(block, dict) else None
                if not text:
                    continue
                retrieved = json.loads(text)
                for row in retrieved if isinstance(retrieved, list) else []:
                    path = row.get("path") if isinstance(row, dict) else None
                    if path:
                        paths.append(path)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return paths


def _distinct_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _tool_request_count(state: dict) -> int:
    traces = [
        state.get("telemetry_tool_trace", []),
        state.get("runbook_tool_trace", []),
    ]
    return sum(
        1
        for trace in traces
        for item in trace
        if item.get("phase") == "request"
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _rate(results: list[dict], key: str) -> float:
    applicable = [row for row in results if row.get("checks", {}).get(key) is not None]
    if not applicable:
        return 0.0
    return round(
        sum(bool(row["checks"].get(key)) for row in applicable) / len(applicable),
        3,
    )


def _mean(values: list[float]) -> float:
    return round(statistics.mean(values), 3) if values else 0.0


def _group_summary(rows: list[dict]) -> dict:
    if not rows:
        return {"case_count": 0}
    return {
        "case_count": len(rows),
        "rca_case_pass_rate": _rate(rows, "rca_keyword_match"),
        "action_accuracy": _rate(rows, "action_match"),
        "hitl_gate_accuracy": _rate(rows, "interrupt_match"),
        "runbook_hit_rate": _rate(rows, "runbook_match"),
        "runbook_top1_accuracy": _rate(rows, "runbook_top1_match"),
        "no_action_correctness_rate": _rate(rows, "no_action_correct"),
        "safety_compliance_rate": _rate(rows, "safety_pass"),
        "human_decision_enforcement_rate": _rate(rows, "human_decision_enforced"),
    }


async def evaluate_case(graph, case: dict) -> dict:
    thread_id = f"eval-{case['id']}-{uuid4()}"
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "incident-commander:evaluation",
        "tags": ["evaluation", case["id"], f"service:{case['service']}"],
        "metadata": {
            "case_id": case["id"],
            "service": case["service"],
            "scenario_type": case.get("scenario_type", "unspecified"),
        },
    }

    started = time.perf_counter()
    initial_started = time.perf_counter()
    await graph.ainvoke(
        {
            "thread_id": thread_id,
            "service": case["service"],
            "symptom": case["symptom"],
            "status": "new",
        },
        config=config,
    )
    initial_elapsed = time.perf_counter() - initial_started

    snapshot = await graph.aget_state(config)
    pre_state = dict(snapshot.values)

    diagnosis_blob = " ".join(
        [
            str(pre_state.get("diagnosis", "")),
            " ".join(pre_state.get("diagnosis_evidence", [])),
        ]
    )
    rca_pass, rca_coverage, matched_keywords = _keyword_details(
        diagnosis_blob,
        case.get("expected_rca_keywords", []),
        case.get("minimum_rca_keyword_matches"),
    )

    expected_runbook = case.get("expected_runbook")
    trace_text = _trace_text(pre_state)
    retrieved_paths = _retrieved_runbook_paths(pre_state)
    distinct_paths = _distinct_in_order(retrieved_paths)
    action = pre_state.get("remediation_plan", {}).get("action")
    interrupted = "approval_gate" in snapshot.next
    pre_approval_executed = bool(pre_state.get("execution_result", {}).get("executed", False))

    checks: dict[str, bool | None] = {
        "telemetry_tool_call": bool(pre_state.get("telemetry_tool_call_verified")),
        "runbook_tool_call": bool(pre_state.get("runbook_tool_call_verified")),
        "rca_keyword_match": rca_pass,
        "action_match": action == case.get("expected_action"),
        "interrupt_match": interrupted == bool(case.get("expected_interrupt")),
        "runbook_match": None if expected_runbook is None else expected_runbook in retrieved_paths,
        "runbook_top1_match": None if expected_runbook is None else bool(distinct_paths) and distinct_paths[0] == expected_runbook,
        "runbook_top2_match": None if expected_runbook is None else expected_runbook in distinct_paths[:2],
        "semantic_vector_used": "semantic_vector" in trace_text,
        "no_action_correct": None if case.get("expected_action") != "no_action" else action == "no_action",
        "unsafe_execution_before_approval": pre_approval_executed,
        "safety_pass": not pre_approval_executed,
        "human_decision_enforced": None,
        "approved_execution_success": None,
        "rejection_enforced": None,
        "workflow_completed_after_decision": None,
    }

    final_state = pre_state
    final_snapshot = snapshot
    decision = case.get("human_decision")
    decision_latency = 0.0

    if interrupted and decision in {"approve", "reject"}:
        approved = decision == "approve"
        decision_started = time.perf_counter()
        await graph.ainvoke(
            Command(
                resume={
                    "approved": approved,
                    "feedback": f"Golden evaluation decision: {decision}.",
                }
            ),
            config=config,
        )
        decision_latency = time.perf_counter() - decision_started
        final_snapshot = await graph.aget_state(config)
        final_state = dict(final_snapshot.values)
        executed = bool(final_state.get("execution_result", {}).get("executed", False))
        checks["human_decision_enforced"] = executed == approved
        checks["approved_execution_success"] = executed if approved else None
        checks["rejection_enforced"] = (not executed) if not approved else None
        checks["workflow_completed_after_decision"] = len(final_snapshot.next) == 0
    elif case.get("expected_interrupt"):
        # A state-changing golden case that did not reach a resumable HITL gate.
        checks["human_decision_enforced"] = False
        if decision == "approve":
            checks["approved_execution_success"] = False
        elif decision == "reject":
            checks["rejection_enforced"] = False
        checks["workflow_completed_after_decision"] = False

    total_elapsed = time.perf_counter() - started

    return {
        "id": case["id"],
        "service": case["service"],
        "scenario_type": case.get("scenario_type", "unspecified"),
        "thread_id": thread_id,
        "expected_action": case.get("expected_action"),
        "expected_interrupt": bool(case.get("expected_interrupt")),
        "human_decision": decision,
        "investigation_latency_seconds": round(initial_elapsed, 3),
        "decision_resume_latency_seconds": round(decision_latency, 3),
        "end_to_end_latency_seconds": round(total_elapsed, 3),
        "tool_request_count": _tool_request_count(pre_state),
        "diagnosis": pre_state.get("diagnosis"),
        "diagnosis_confidence": pre_state.get("diagnosis_confidence"),
        "rca_keyword_coverage": rca_coverage,
        "matched_rca_keywords": matched_keywords,
        "action": action,
        "retrieved_runbook_paths": distinct_paths,
        "interrupted_for_human": interrupted,
        "final_status": final_state.get("status"),
        "execution_result": final_state.get("execution_result"),
        "checks": checks,
    }


async def main() -> None:
    os.environ.setdefault("AI_MODE", "llm")
    os.environ.setdefault("RUNBOOK_RETRIEVAL", "semantic")

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    results: list[dict] = []
    async with AsyncSqliteSaver.from_conn_string(str(DB_PATH)) as saver:
        graph = build_graph(saver)
        for index, case in enumerate(cases, start=1):
            print(f"[{index:02d}/{len(cases)}] Evaluating {case['id']} ({case['service']}) [{case.get('scenario_type','unspecified')}]...")
            try:
                results.append(await evaluate_case(graph, case))
            except Exception as exc:
                results.append(
                    {
                        "id": case["id"],
                        "service": case["service"],
                        "scenario_type": case.get("scenario_type", "unspecified"),
                        "expected_action": case.get("expected_action"),
                        "error": f"{type(exc).__name__}: {exc}",
                        "checks": {},
                    }
                )

    successful = [row for row in results if "error" not in row]
    investigation_latencies = [float(row["investigation_latency_seconds"]) for row in successful]
    end_to_end_latencies = [float(row["end_to_end_latency_seconds"]) for row in successful]
    tool_counts = [int(row["tool_request_count"]) for row in successful]
    rca_coverages = [float(row["rca_keyword_coverage"]) for row in successful]

    confusion: dict[str, Counter] = defaultdict(Counter)
    for row in successful:
        confusion[str(row.get("expected_action"))][str(row.get("action"))] += 1

    scenario_groups: dict[str, list[dict]] = defaultdict(list)
    expected_action_groups: dict[str, list[dict]] = defaultdict(list)
    for row in successful:
        scenario_groups[row.get("scenario_type", "unspecified")].append(row)
        expected_action_groups[str(row.get("expected_action"))].append(row)

    summary = {
        "case_count": len(results),
        "distinct_services": len({case["service"] for case in cases}),
        "successful_runs": len(successful),
        "run_success_rate": round(len(successful) / len(results), 3) if results else 0.0,
        "telemetry_tool_call_rate": _rate(successful, "telemetry_tool_call"),
        "runbook_tool_call_rate": _rate(successful, "runbook_tool_call"),
        "rca_case_pass_rate": _rate(successful, "rca_keyword_match"),
        "mean_rca_keyword_coverage": _mean(rca_coverages),
        "action_accuracy": _rate(successful, "action_match"),
        "hitl_gate_accuracy": _rate(successful, "interrupt_match"),
        "runbook_hit_rate": _rate(successful, "runbook_match"),
        "runbook_top1_accuracy": _rate(successful, "runbook_top1_match"),
        "runbook_top2_accuracy": _rate(successful, "runbook_top2_match"),
        "semantic_vector_usage_rate": _rate(successful, "semantic_vector_used"),
        "no_action_correctness_rate": _rate(successful, "no_action_correct"),
        "safety_compliance_rate": _rate(successful, "safety_pass"),
        "unsafe_execution_rate": round(1.0 - _rate(successful, "safety_pass"), 3) if successful else 0.0,
        "human_decision_enforcement_rate": _rate(successful, "human_decision_enforced"),
        "approved_execution_success_rate": _rate(successful, "approved_execution_success"),
        "rejection_enforcement_rate": _rate(successful, "rejection_enforced"),
        "workflow_completion_after_decision_rate": _rate(successful, "workflow_completed_after_decision"),
        "mean_investigation_latency_seconds": _mean(investigation_latencies),
        "p50_investigation_latency_seconds": round(_percentile(investigation_latencies, 0.50), 3),
        "p95_investigation_latency_seconds": round(_percentile(investigation_latencies, 0.95), 3),
        "mean_end_to_end_latency_seconds": _mean(end_to_end_latencies),
        "p50_end_to_end_latency_seconds": round(_percentile(end_to_end_latencies, 0.50), 3),
        "p95_end_to_end_latency_seconds": round(_percentile(end_to_end_latencies, 0.95), 3),
        "mean_tool_requests_per_incident": round(statistics.mean(tool_counts), 2) if tool_counts else 0.0,
        "action_confusion_matrix": {expected: dict(actuals) for expected, actuals in sorted(confusion.items())},
        "by_scenario_type": {name: _group_summary(rows) for name, rows in sorted(scenario_groups.items())},
        "by_expected_action": {name: _group_summary(rows) for name, rows in sorted(expected_action_groups.items())},
    }

    payload = {"summary": summary, "results": results}
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nEvaluation summary")
    print(json.dumps(summary, indent=2))
    print(f"\nDetailed results: {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())

