from fastapi.testclient import TestClient


def test_end_to_end_hitl_approval_and_persistence(tmp_path, monkeypatch):
    """CI-safe end-to-end test: API -> graph -> HITL -> trusted executor -> persisted read."""
    monkeypatch.setenv("AI_MODE", "deterministic")
    monkeypatch.setenv("RUNBOOK_RETRIEVAL", "lexical")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("RUN_LLM_TESTS", "0")
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "stage4d-integration.sqlite"))

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
        payload = created.json()
        thread_id = payload["thread_id"]

        # checkout-api deterministically proposes a state-changing action,
        # therefore the graph must pause before executing anything.
        assert "approval_gate" in payload["next"]
        assert payload["state"]["remediation_plan"]["requires_human_approval"] is True

        approved = client.post(
            f"/incidents/{thread_id}/decision",
            json={
                "approved": True,
                "feedback": "Stage 4D CI approval path",
            },
        )
        assert approved.status_code == 200
        approved_state = approved.json()["state"]
        assert approved_state["approval"]["approved"] is True
        assert approved_state["execution_result"]["executed"] is True
        assert approved_state["execution_result"]["mode"] == "simulation"

        persisted = client.get(f"/incidents/{thread_id}")
        assert persisted.status_code == 200
        persisted_state = persisted.json()["state"]
        assert persisted_state["approval"]["approved"] is True
        assert persisted_state["execution_result"]["executed"] is True
        assert persisted_state["status"] == "completed"

        history = client.get(f"/incidents/{thread_id}/history")
        assert history.status_code == 200
        assert history.json()["checkpoint_count"] >= 2


def test_end_to_end_hitl_rejection_blocks_execution(tmp_path, monkeypatch):
    """Regression test for the most important safety invariant."""
    monkeypatch.setenv("AI_MODE", "deterministic")
    monkeypatch.setenv("RUNBOOK_RETRIEVAL", "lexical")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("RUN_LLM_TESTS", "0")
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "stage4d-rejection.sqlite"))

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
        payload = created.json()
        thread_id = payload["thread_id"]
        assert "approval_gate" in payload["next"]

        rejected = client.post(
            f"/incidents/{thread_id}/decision",
            json={
                "approved": False,
                "feedback": "Stage 4D CI rejection path",
            },
        )
        assert rejected.status_code == 200
        state = rejected.json()["state"]
        assert state["approval"]["approved"] is False
        assert state["execution_result"]["executed"] is False
        assert state["execution_result"]["reason"] == "Human rejected the proposed remediation."

