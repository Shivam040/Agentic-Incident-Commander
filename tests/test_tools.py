from incident_commander.tools.remediation import execute_remediation
from incident_commander.tools.runbooks import search_runbooks
from incident_commander.tools.telemetry import get_service_metrics


def test_checkout_metrics_are_degraded():
    metrics = get_service_metrics("checkout-api")
    assert metrics["status"] == "degraded"
    assert metrics["error_rate"] >= 0.10


def test_runbook_retrieval_returns_database_guidance():
    results = search_runbooks("database connection pool timeout", top_k=2)
    assert results
    assert any("database" in item["content"].lower() for item in results)


def test_remediation_refuses_without_approval():
    result = execute_remediation("checkout-api", "restart_service", False)
    assert result["executed"] is False


def test_remediation_simulates_after_approval():
    result = execute_remediation("checkout-api", "restart_service", True)
    assert result["executed"] is True
    assert result["mode"] == "simulation"

