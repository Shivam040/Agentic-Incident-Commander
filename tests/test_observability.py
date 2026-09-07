from prometheus_client import generate_latest

from incident_commander.observability import (
    record_hitl_decision,
    record_remediation,
    record_safety_block,
    record_workflow,
)


def test_stage4_prometheus_metric_families_are_exposed():
    record_workflow("test", "completed", 0.01)
    record_hitl_decision(True)
    record_remediation("scale_out", False)
    record_safety_block("test_guard")

    body = generate_latest().decode("utf-8")

    assert "incident_commander_workflow_runs_total" in body
    assert "incident_commander_workflow_duration_seconds" in body
    assert "incident_commander_hitl_decisions_total" in body
    assert "incident_commander_remediation_results_total" in body
    assert "incident_commander_safety_blocks_total" in body

