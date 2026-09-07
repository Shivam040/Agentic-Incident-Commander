from fastapi.testclient import TestClient


def test_stage4_api_observability_and_persistent_hitl(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_MODE", "deterministic")
    monkeypatch.setenv("RUNBOOK_RETRIEVAL", "lexical")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "stage4-test.sqlite"))

    from incident_commander.api import app

    with TestClient(app) as client:
        created = client.post(
            "/incidents",
            json={
                "service": "checkout-api",
                "symptom": "latency and elevated 503 errors",
            },
        )
        assert created.status_code == 200
        assert created.headers.get("X-Request-ID")

        payload = created.json()
        thread_id = payload["thread_id"]
        assert "approval_gate" in payload["next"]

        rejected = client.post(
            f"/incidents/{thread_id}/decision",
            json={"approved": False, "feedback": "CI rejection path"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["state"]["execution_result"]["executed"] is False

        incident = client.get(f"/incidents/{thread_id}")
        assert incident.status_code == 200
        assert incident.json()["state"]["approval"]["approved"] is False

        history = client.get(f"/incidents/{thread_id}/history")
        assert history.status_code == 200
        assert history.json()["checkpoint_count"] >= 1

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["observability"]["prometheus_metrics"] is True

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "incident_commander_http_requests_total" in metrics.text
        assert "incident_commander_workflow_runs_total" in metrics.text

