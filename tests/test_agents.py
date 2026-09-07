from incident_commander.agents.rca_agent import rca_agent
from incident_commander.agents.remediation_agent import remediation_agent


def test_rca_finds_high_severity_signals():
    state = {
        "metrics": {
            "error_rate": 0.18,
            "p95_latency_ms": 1800,
            "cpu_percent": 92,
        },
        "logs": ["ERROR database timeout", "WARN connection pool utilization=96%"],
    }
    result = rca_agent(state)
    assert result["diagnosis_confidence"] >= 0.8
    assert "database" in result["diagnosis"].lower()


def test_remediation_proposes_reviewed_action():
    state = {
        "metrics": {"cpu_percent": 92},
        "logs": ["ERROR database timeout"],
    }
    result = remediation_agent(state)
    plan = result["remediation_plan"]
    assert plan["requires_human_approval"] is True
    assert plan["action"] in {"restart_service", "scale_out"}

