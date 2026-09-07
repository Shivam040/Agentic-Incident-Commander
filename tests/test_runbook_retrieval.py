from incident_commander.tools.runbooks import search_runbooks


def test_lexical_cpu_query_prefers_high_latency(monkeypatch):
    monkeypatch.setenv("RUNBOOK_RETRIEVAL", "lexical")
    results = search_runbooks(
        "high CPU worker saturation latency 503",
        top_k=2,
    )
    assert results
    assert results[0]["path"] == "high_latency.md"
    assert results[0]["retrieval_mode"] == "lexical"


def test_lexical_database_query_returns_database_runbook(monkeypatch):
    monkeypatch.setenv("RUNBOOK_RETRIEVAL", "lexical")
    results = search_runbooks(
        "database connection pool timeout 503",
        top_k=2,
    )
    assert results
    assert any(item["path"] == "database_pressure.md" for item in results)

